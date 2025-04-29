import logging
import sys, traceback
import threading
import os
import csv
import time
import datetime
from engine.Manager.ConnectionManage.ConnectionManage import ConnectionManage
from proxmoxer import ProxmoxAPI
from proxmoxer.core import ResourceException
from proxmoxer.backends import ssh_paramiko
from proxmoxer.tools import Tasks
from engine.Configuration.ExperimentConfigIO import ExperimentConfigIO
from engine.Configuration.SystemConfigIO import SystemConfigIO
from engine.Configuration.UserPool import UserPool
from threading import RLock

class ConnectionManageProxVNC(ConnectionManage):
    def __init__(self, username=None, password=None):
        logging.debug("ConnectionManageGuacRDP(): instantiated")
        ConnectionManage.__init__(self)
        self.proxapi = None
        self.proxssh = None
        self.eco = ExperimentConfigIO.getInstance()
        self.usersConnsStatus = {}
        self.lock = RLock()
        self.s = SystemConfigIO()
        self.sshusername = None
        self.sshpassword = None

    def getProxAPI(self, configname, username=None, password=None):
        logging.debug("ProxmoxManage: getProxAPI(): instantiated")
        try:
            vmHostname, vmserversshport, rdiplayhostname, chatserver, challengesserver, users_file = self.eco.getExperimentServerInfo(configname)
            server = vmHostname
            self.nodename = self.eco.getExperimentJSONFileData(configname)["xml"]["testbed-setup"]["vm-set"]["base-groupname"]
            splithostname = vmHostname.split("://")
            if len(splithostname) > 1:
                rsplit = splithostname[1]
                if len(rsplit.split(":")) > 1:
                    port = rsplit.split(":")[1].split("/")[0]
                server = rsplit.split("/")[0]

            if self.proxapi == None and username != None and password != None and username.strip() != "" and password.strip() != "":
                self.proxapi = ProxmoxAPI(server, port=port, user=username, password=password, verify_ssl=False)
            elif self.proxapi != None and username != None and password != None and username.strip() != "" and password.strip() != "":
                self.proxapi = None
                self.proxapi = ProxmoxAPI(server, port=port, user=username, password=password, verify_ssl=False)

            return self.proxapi, self.nodename
        except Exception:
            logging.error("Error in getProxAPI(): An error occured when trying to connect to proxmox")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
            self.proxapi = None
            return None

    def getProxSSH(self, configname, username=None, password=None):
        logging.debug("ProxmoxManage: getProxSSH(): instantiated")
        try:
            
            vmHostname, vmserversshport, rdisplayhostname, chatserver, challengesserver, users_file = self.eco.getExperimentServerInfo(configname)
            server = vmHostname
            user = None
            if len(username) > 4:
                user = username[:-4]
            splithostname = vmHostname.split("://")
            if len(splithostname) > 1:
                rsplit = splithostname[1]
                server = rsplit.split("/")[0]
                server = server.split(":")[0]
            if self.proxssh == None and user != None and password != None and user.strip() != "" and password.strip() != "":
                self.proxssh = ssh_paramiko.SshParamikoSession(server,port=vmserversshport, user=user,password=password)
                self.sshusername = user
                self.sshpassword = password
            elif self.proxssh != None and user != None and password != None and user.strip() != "" and password.strip() != "":
                self.proxssh = None
                self.proxssh = ssh_paramiko.SshParamikoSession(server,port=vmserversshport, user=user,password=password)
                self.sshusername = user
                self.sshpassword = password
            return self.proxssh
        except Exception:
            logging.error("Error in getProxSSH(): An error occured when trying to connect to proxmox with ssh")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
            self.proxssh = None
            return None

    def executeSSH(self, command, sudo=True):
        feed_password = False
        if sudo and self.sshusername != "root":
            command = "sudo -S -p '' %s" % command
            feed_password = self.sshpassword is not None and len(self.sshpassword) > 0
        stdin, stdout, stderr = self.proxssh.ssh_client.exec_command(command)
        if feed_password:
            stdin.write(self.sshpassword + "\n")
            stdin.flush()
        return {'out': stdout.readlines(), 
                'err': stderr.readlines(),
                'retval': stdout.channel.recv_exit_status()}        

    def basic_blocking_task_status(self, proxmox_api, task_id, caller=""):
        logging.debug("ProxmoxManage: basic_blocking_task_status(): instantiated by " + str(caller))
        Tasks.blocking_status(proxmox_api, task_id)

    #abstractmethod
    def createConnections(self, configname, proxHostname, username, password, maxConnections="", maxConnectionsPerUser="", width="", height="", bitdepth="", creds_file="", itype="", name=""):
        logging.debug("createConnections(): instantiated")
        t = threading.Thread(target=self.runCreateConnections, args=(configname, proxHostname, username, password, maxConnections, maxConnectionsPerUser, width, height, bitdepth, creds_file, itype, name))
        self.writeStatus+=1
        t.start()
        return 0

    def runCreateConnections(self, configname, proxHostname, musername, mpassword, maxConnections="", maxConnectionsPerUser="", width="", height="", bitdepth="", creds_file="", itype="", name=""):
        logging.debug("runCreateConnections(): instantiated")
        #call guac backend API to make connections as specified in config file and then set the complete status
        rolledoutjson = self.eco.getExperimentVMRolledOut(configname)
        validconnsnames = self.eco.getValidVMsFromTypeName(configname, itype, name, rolledoutjson)

        userpool = UserPool()
        usersConns = userpool.generateUsersConns(configname, creds_file=creds_file)

        try:
            #get accessors to the proxmox api and ssh
            try:
                proxapi, nodename = self.getProxAPI(configname, musername, mpassword)
                if proxapi == None:
                    return None

                proxssh = self.getProxSSH(configname, username=musername,password=mpassword)
                if proxssh == None:
                    return None
            except Exception:
                logging.error("Error in runCreateConnections(): An error occured when trying to connect to proxmox")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
                return None
            #get the list of all users and pools
            try:
                res = proxapi.access.users.get()
                users = []
                for user_info in res:
                    user = user_info['userid']
                    if len(user.strip()) > 4 and user[-4:] == "@pam":
                        users.append(user_info['userid'][:-4])
            except Exception:
                logging.error("Error in runCreateConnections(): An error occured when trying to get users")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)

            try:
                res = proxapi.pools.get()
                pools = []
                for pool_info in res:
                    pools.append(pool_info['poolid'])
            except Exception:
                logging.error("Error in runCreateConnections(): An error occured when trying to get users")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)

            #get the list of all VMs
            try:
                allinfo = proxapi.cluster.resources.get(type='vm')
            except Exception:
                logging.error("Error in runCreateConnections: An error occured when trying to get cluster info")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)

            if allinfo is None:
                logging.error("runCreateConnections(): info is None")
                return -1
            vmname_id = {}
            for vmiter in allinfo:
                #GET UUID
                vmname_id[vmiter['name']] = vmiter['vmid']

            try:
                created_users_lin = []
                created_users = []
                created_pools = []
                created_pool_privs = []
                added_vms = []

                for (username, password) in usersConns:
                    for conn in usersConns[(username, password)]:
                        cloneVMName = conn[0]
                        vmServerIP = conn[1]
                        vrdpPort = conn[2]
                        #only if this is a specific connection to create; based on itype and name
                        if cloneVMName in validconnsnames:
                            #if user doesn't exist, create it
                            result = self.executeSSH("/usr/sbin/useradd " + username)
                            if username not in users and username not in created_users_lin:
                                logging.debug( "Creating User: " + username)
                                try:
                                    # result = self.proxssh._exec(shlex.split("/usr/sbin/useradd " + username))
                                    result = self.executeSSH("/usr/sbin/useradd " + username)
                                    if result != None and 'err' in result and "already exists" in result['err']:
                                        logging.debug("User" + username + " already exists; skipping...")
                                    else:
                                        created_users_lin.append(username)
                                except ResourceException:
                                    logging.warning("runCreateConnections(): Pool " + username + " already exists, skipping.")
                                    # exc_type, exc_value, exc_traceback = sys.exc_info()
                                    # traceback.print_exception(exc_type, exc_value, exc_traceback)                              
                                except Exception:
                                    logging.error("runCreateConnections(): Error in runCreateConnections(): when trying to create user.")
                                    exc_type, exc_value, exc_traceback = sys.exc_info()
                                    traceback.print_exception(exc_type, exc_value, exc_traceback)
                            if username not in users and username not in created_users:
                                try:
                                    result = self.proxapi.access.users.post(userid=username+"@pam", password=password)
                                    if result != None and len(result) > 1 and 'already exists' in result[1]:
                                        logging.debug("User" + username + " already exists; skipping...")
                                    else:
                                        created_users.append(username)
                                except ResourceException:
                                    logging.warning("runCreateConnections(): Pool " + username + " already exists, skipping.")
                                    # exc_type, exc_value, exc_traceback = sys.exc_info()
                                    # traceback.print_exception(exc_type, exc_value, exc_traceback)                                                                 
                                except Exception:
                                    logging.error("runCreateConnections(): Error in runCreateConnections(): when trying to create user.")
                                    exc_type, exc_value, exc_traceback = sys.exc_info()
                                    traceback.print_exception(exc_type, exc_value, exc_traceback)

                            if username not in pools and username not in created_pools:
                                logging.debug( "Creating Pool: " + username)
                                try:
                                    result = proxapi.pools.create(poolid=username, comment="Pool for user " + username)
                                    if result == None:
                                        created_pools.append(username)
                                except ResourceException:
                                    logging.warning("runCreateConnections(): Pool " + username + " already exists, skipping.")
                                    # exc_type, exc_value, exc_traceback = sys.exc_info()
                                    # traceback.print_exception(exc_type, exc_value, exc_traceback)                                    
                                except Exception:
                                    logging.error("runCreateConnections(): Error in runCreateConnections(): when trying to create pool: " + username)
                                    # exc_type, exc_value, exc_traceback = sys.exc_info()
                                    # traceback.print_exception(exc_type, exc_value, exc_traceback)
                            if username not in created_pool_privs:
                                #now give user privs on the pool:
                                logging.debug( "Setting Pool Privs for: " + username)
                                try:
                                    result = proxapi.access.acl.put(path='/pool/'+username, users=username+"@pam", roles='PVEVMUser, PVEPoolUser', propagate=1)
                                    if result == None:
                                        created_pool_privs.append(username)
                                except ResourceException:
                                    logging.warning("runCreateConnections(): Pool Privs for " + username + " already exist, skipping.")
                                    # exc_type, exc_value, exc_traceback = sys.exc_info()
                                    # traceback.print_exception(exc_type, exc_value, exc_traceback)                                    
                                except Exception:
                                    logging.error("runCreateConnections(): Error in runCreateConnections(): when trying to create pool privs for: " + username)
                                    # exc_type, exc_value, exc_traceback = sys.exc_info()
                                    # traceback.print_exception(exc_type, exc_value, exc_traceback)
                            
                            if cloneVMName not in added_vms:
                                #add vms with vrdp enabled to the pool
                                logging.debug( "Adding VMs to pool: " + username)
                                try:
                                    if cloneVMName not in vmname_id:
                                        logging.debug("VM " + cloneVMName + " not found; skipping...")
                                        continue
                                    vmid = vmname_id[cloneVMName]
                                    # if the VM is not already in the pool, add it
                                    result = proxapi.pools.put(poolid=username, vms=vmid)
                                    if result == None:
                                        logging.debug("runCreateConnections(): Added VM: " + str(vmid) + " to pool: " + str(username))
                                        added_vms.append(vmid)
                                except ResourceException:
                                    logging.warning("runCreateConnections(): VM " + str(vmid) + " already in pool: " + username + " skipping.")
                                    # exc_type, exc_value, exc_traceback = sys.exc_info()
                                    # traceback.print_exception(exc_type, exc_value, exc_traceback)                                    
                                except Exception:
                                    logging.error("runCreateConnections(): Error in runCreateConnections(): when trying to add vm to pool: " + username)
                                    # exc_type, exc_value, exc_traceback = sys.exc_info()
                                # traceback.print_exception(exc_type, exc_value, exc_traceback)

            except Exception:
                    logging.error("runCreateConnections(): Error in runCreateConnections(): when trying to add connection.")
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    traceback.print_exception(exc_type, exc_value, exc_traceback)
            logging.debug("runCreateConnections(): Complete...")
        except Exception:
            logging.error("runCreateConnections(): Error in runCreateConnections(): An error occured ")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
        finally:
            self.writeStatus-=1

    #abstractmethod
    def clearAllConnections(self, configname, proxHostname, username, password, exceptions=[]):
        logging.debug("clearAllConnections(): instantiated")
        t = threading.Thread(target=self.runClearAllConnections, args=(configname, proxHostname, username, password, exceptions))
        self.writeStatus+=1
        t.start()
        return 0

    def runClearAllConnections(self, configname, proxHostname, musername, mpassword, exceptions=["root","nathanvms", "ana", "arodriguez", "jacosta", "jcacosta"]):
        logging.debug("runClearAllConnections(): instantiated")
        try:
            #get accessors to the proxmox api and ssh
            try:
                proxapi, nodename = self.getProxAPI(configname, musername, mpassword)
                if proxapi == None:
                    return None

                proxssh = self.getProxSSH(configname, musername, mpassword)
                if proxssh == None:
                    return None
            except Exception:
                logging.error("Error in runClearAllConnections(): An error occured when trying to connect to proxmox")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
                return None
            #get the list of all users and pools
            try:
                res = proxapi.access.users.get()
                users = []
                for user_info in res:
                    user = user_info['userid']
                    if len(user.strip()) > 4 and user[-4:] == "@pam":
                        users.append(user_info['userid'][:-4])
            except Exception:
                logging.error("Error in runClearAllConnections(): An error occured when trying to get users")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)

            try:
                res = proxapi.pools.get()
                pools = []
                for pool_info in res:
                    pools.append(pool_info['poolid'])
            except Exception:
                logging.error("Error in runClearAllConnections(): An error occured when trying to get users")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)

            #get the list of all VMs
            try:
                allinfo = proxapi.cluster.resources.get(type='vm')
            except Exception:
                logging.error("Error in runClearAllConnections: An error occured when trying to get cluster info")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)

            users_removed_lin = []
            users_removed = []
            pools_removed = []

            #for each pool, remove all users from the pool and then the pool itself
            for pool in pools:
                if pool in exceptions or pool in pools_removed:
                    continue
                try:
                    members_ds = proxapi.pools(pool).get()
                    members = []
                    for member in members_ds['members']:
                        members.append(str(member['vmid']))
                except ResourceException:
                    logging.warning("runClearAllConnections(): Pool " + pool + " does not exist, skipping.")
                    # exc_type, exc_value, exc_traceback = sys.exc_info()
                    # traceback.print_exception(exc_type, exc_value, exc_traceback)                                    
                except Exception:
                    logging.error("runClearAllConnections(): error when trying to remove pool: " + pool)
                    # exc_type, exc_value, exc_traceback = sys.exc_info()
                    # traceback.print_exception(exc_type, exc_value, exc_traceback)

                try:
                    logging.debug( "Removing VMs: " + str(members))
                    result = proxapi.pools(pool).put(delete=1,vms=",".join(members))
                except ResourceException:
                    logging.warning("runClearAllConnections(): members do not exist" + str(members) + ", skipping.")
                    # exc_type, exc_value, exc_traceback = sys.exc_info()
                    # traceback.print_exception(exc_type, exc_value, exc_traceback)                                    
                except Exception:
                    logging.error("runClearAllConnections(): error when trying to remove member: " + member)
                    # exc_type, exc_value, exc_traceback = sys.exc_info()
                    # traceback.print_exception(exc_type, exc_value, exc_traceback)

                logging.debug( "Removing Pool: " + pool)
                try:
                    result = proxapi.pools.delete(poolid=pool)
                    if result == None:
                        pools_removed.append(pool)
                except ResourceException:
                    logging.warning("runClearAllConnections(): Pool " + pool + " already exists, skipping.")
                    # exc_type, exc_value, exc_traceback = sys.exc_info()
                    # traceback.print_exception(exc_type, exc_value, exc_traceback)                                    
                except Exception:
                    logging.error("runClearAllConnections(): error when trying to remove pool: " + pool)
                    # exc_type, exc_value, exc_traceback = sys.exc_info()
                    # traceback.print_exception(exc_type, exc_value, exc_traceback)

            #remove all users except root, ana, and nathan
            for user in users:
                if user in exceptions or user in users_removed_lin:
                    continue
                logging.debug( "Removing User: " + user)
                try:
                    # result = proxssh._exec(shlex.split("userdel " + user))
                    result = self.executeSSH("userdel " + user)
                    if result != None and 'err' in result and "does not exist" in result['err']:
                        logging.debug("User" + user + " does not exist; skipping...")
                    else:
                        users_removed_lin.append(user)
                except ResourceException:
                    logging.warning("runClearAllConnections(): User " + user + " does not exists, skipping.")
                    # exc_type, exc_value, exc_traceback = sys.exc_info()
                    # traceback.print_exception(exc_type, exc_value, exc_traceback)                                    
                except Exception:
                    logging.error("runClearAllConnections(): error when trying to remove user: " + user)
                    # exc_type, exc_value, exc_traceback = sys.exc_info()
                    # traceback.print_exception(exc_type, exc_value, exc_traceback)

                if user in users_removed:
                    continue
                try:
                    result = proxapi.access.users(user+"@pam").delete()
                    if result != None and len(result) > 1 and 'already exists' in result[1]:
                        logging.debug("User" + user + " does not exist; skipping...")
                    else:
                        users_removed.append(user)
                except ResourceException:
                    logging.warning("runClearAllConnections(): User " + user + " does not exists, skipping.")
                    # exc_type, exc_value, exc_traceback = sys.exc_info()
                    # traceback.print_exception(exc_type, exc_value, exc_traceback)                                    
                except Exception:
                    logging.error("runClearAllConnections(): error when trying to remove user: " + user)
                    # exc_type, exc_value, exc_traceback = sys.exc_info()
                    # traceback.print_exception(exc_type, exc_value, exc_traceback)
        except Exception:
            logging.error("Error in runClearAllConnections: An error occured.")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
        finally:
            self.writeStatus-=1

    #abstractmethod
    def removeConnections(self, configname, proxHostname, username, password, creds_file="", itype="", name=""):
        logging.debug("removeConnections(): instantiated")
        t = threading.Thread(target=self.runRemoveConnections, args=(configname,proxHostname, username, password, creds_file, itype, name))
        self.writeStatus+=1
        t.start()
        return 0

    def runRemoveConnections(self, configname, proxHostname, musername, mpassword, creds_file, itype, name):
        logging.debug("runRemoveConnections(): instantiated")
        try:
            rolledoutjson = self.eco.getExperimentVMRolledOut(configname)
            validconnsnames = self.eco.getValidVMsFromTypeName(configname, itype, name, rolledoutjson)

            userpool = UserPool()
            usersConns = userpool.generateUsersConns(configname, creds_file=creds_file)

            #get accessors to the proxmox api and ssh
            try:
                proxapi, nodename = self.getProxAPI(configname, musername, mpassword)
                if proxapi == None:
                    return None

                proxssh = self.getProxSSH(configname, musername, mpassword)
                if proxssh == None:
                    return None
            except Exception:
                logging.error("Error in runClearAllConnections(): An error occured when trying to connect to proxmox")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
                return None
            #get the list of all pools
            try:
                res = proxapi.pools.get()
                pools = []
                for pool_info in res:
                    pools.append(pool_info['poolid'])
            except Exception:
                logging.error("Error in runClearAllConnections(): An error occured when trying to get users")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)

            users_removed_lin = []
            users_removed = []
            pools_removed = []

            for (username, password) in usersConns:
                logging.debug( "Removing Pool and User: " + username)
                try:
                    for conn in usersConns[(username, password)]:
                        cloneVMName = conn[0]
                        if cloneVMName in validconnsnames:
                            #get vms in pool
                            
                            if username not in pools or cloneVMName not in validconnsnames or username == "nathanvms" or username == "ana" or username in pools_removed:
                                continue
                            try:
                                members_ds = proxapi.pools(username).get()
                                members = []
                                #get vms in pool
                                for member in members_ds['members']:
                                    members.append(str(member['vmid']))
                            except ResourceException:
                                logging.warning("runClearAllConnections(): Pool " + username + " already exists, skipping.")
                                # exc_type, exc_value, exc_traceback = sys.exc_info()
                                # traceback.print_exception(exc_type, exc_value, exc_traceback)                                    
                            except Exception:
                                logging.error("runClearAllConnections(): error when trying to remove pool: " + username)
                                # exc_type, exc_value, exc_traceback = sys.exc_info()
                                # traceback.print_exception(exc_type, exc_value, exc_traceback)

                            #remove vms from pool
                            try:
                                logging.debug( "Removing VMs: " + str(members))
                                result = proxapi.pools(username).put(delete=1,vms=",".join(members))
                            except ResourceException:
                                logging.warning("runRemoveConnections(): members do not exist" + str(members) + ", skipping.")
                                # exc_type, exc_value, exc_traceback = sys.exc_info()
                                # traceback.print_exception(exc_type, exc_value, exc_traceback)                                    
                            except Exception:
                                logging.error("runRemoveConnections(): error when trying to remove member: " + member)
                                # exc_type, exc_value, exc_traceback = sys.exc_info()
                                # traceback.print_exception(exc_type, exc_value, exc_traceback)

                            #remove the pool
                            logging.debug( "Removing Pool: " + username)
                            try:
                                result = proxapi.pools.delete(poolid=username)
                                if result == None:
                                    pools_removed.append(username)
                            except ResourceException:
                                logging.warning("runRemoveConnections(): Pool " + username + " does not exists, skipping.")
                                # exc_type, exc_value, exc_traceback = sys.exc_info()
                                # traceback.print_exception(exc_type, exc_value, exc_traceback)                                    
                            except Exception:
                                logging.error("runRemoveConnections(): error when trying to remove pool: " + username)
                                # exc_type, exc_value, exc_traceback = sys.exc_info()
                                # traceback.print_exception(exc_type, exc_value, exc_traceback)

                            #remove user
                            if username in users_removed_lin:
                                continue
                            logging.debug( "Removing User: " + username)
                            try:
                                # result = proxssh._exec(shlex.split("userdel " + user))
                                result = self.executeSSH("userdel " + username)
                                if result != None and len(result) > 1 and 'err' in result and "does not exist" in result['err']:
                                    logging.debug("User" + username + " does not exist; skipping...")
                                else:
                                    users_removed_lin.append(username)
                            except ResourceException:
                                logging.warning("runRemoveConnections(): User " + username + " does not exist, skipping.")
                                # exc_type, exc_value, exc_traceback = sys.exc_info()
                                # traceback.print_exception(exc_type, exc_value, exc_traceback)                                    
                            except Exception:
                                logging.error("runRemoveConnections(): error when trying to remove user: " + username)
                                # exc_type, exc_value, exc_traceback = sys.exc_info()
                                # traceback.print_exception(exc_type, exc_value, exc_traceback)

                            if username in users_removed:
                                continue
                            try:
                                result = proxapi.access.users(username+"@pam").delete()
                                if result != None and  len(result) > 1 and "does not exist" in result[1]:
                                    logging.debug("User" + username + " does not exist; skipping...")
                                else:
                                    users_removed.append(username)
                            except ResourceException:
                                logging.warning("runRemoveConnections(): User " + username + " does not exists, skipping.")
                                # exc_type, exc_value, exc_traceback = sys.exc_info()
                                # traceback.print_exception(exc_type, exc_value, exc_traceback)                                    
                            except Exception:
                                logging.error("runRemoveConnections(): error when trying to remove user: " + username)
                                # exc_type, exc_value, exc_traceback = sys.exc_info()
                                # traceback.print_exception(exc_type, exc_value, exc_traceback)

                except Exception:
                        logging.error("runRemoveConnections(): Error in runRemoveConnections(): when trying to remove connection.")
                        exc_type, exc_value, exc_traceback = sys.exc_info()
                        traceback.print_exception(exc_type, exc_value, exc_traceback)
            logging.debug("runRemoveConnections(): Complete...")
        finally:
            self.writeStatus-=1

    #abstractmethod
    def openConnection(self, configname, experimentid, vmid):
        logging.debug("openConnection(): instantiated")
        t = threading.Thread(target=self.runOpenConnection, args=(configname,))
        self.writeStatus+=1
        t.start()
        return 0

    def runOpenConnection(self, configname, experimentid, vmid):
        logging.debug("runOpenConnection(): instantiated")
        #open an RDP session using configuration from systemconfigIO to the specified experimentid/vmid
        self.writeStatus-=1

    #abstractmethod
    def getConnectionManageStatus(self):
        logging.debug("getConnectionManageStatus(): instantiated")
        return {"readStatus" : self.readStatus, "writeStatus" : self.writeStatus, "usersConnsStatus" : self.usersConnsStatus}
    
    def getConnectionManageRefresh(self, configname, proxHostname, musername, mpassword):
        logging.debug("getConnectionManageStatus(): instantiated")
        try:
            self.lock.acquire()
            self.usersConnsStatus.clear()

            # if pool name with username exists, then "connection exists"
            # check tasks and look for those without end time; if type is vnxproxy, get username; that user is connected
            try:
                proxapi, nodename = self.getProxAPI(configname, musername, mpassword)
                if proxapi == None:
                    return None

                proxssh = self.getProxSSH(configname, musername, mpassword)
                if proxssh == None:
                    return None
            except Exception:
                logging.error("Error in getConnectionManageRefresh(): An error occured when trying to connect to proxmox")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
                return None
            
            #get vmid -> vmname mapping
            vmid_name = {}
            try:
                allinfo = proxapi.cluster.resources.get(type='vm')
            except Exception:
                logging.error("Error in getConnectionManageRefresh: An error occured when trying to get cluster info")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
            for vmiter in allinfo:
                #GET UUID
                vmname = vmiter['name']
                vmid = vmiter['vmid']
                vmid_name[str(vmid)] = vmname

            #get the list of all pools
            try:
                res = proxapi.pools.get()
                pools = {}
                for pool_info in res:
                    pool_id = pool_info['poolid']
                    pools[pool_id] = []
                    try:
                        members_ds = proxapi.pools(pool_id).get()
                        for member in members_ds['members']:
                            pools[pool_id].append(vmid_name[str(member['vmid'])])
                    except ResourceException:
                        logging.warning("runClearAllConnections(): Pool " + pool_id + " does not exist, skipping.")
                        # exc_type, exc_value, exc_traceback = sys.exc_info()
                        # traceback.print_exception(exc_type, exc_value, exc_traceback)                                    
                    except Exception:
                        logging.error("runClearAllConnections(): error when trying to remove pool: " + pool_id)
                        # exc_type, exc_value, exc_traceback = sys.exc_info()
                        # traceback.print_exception(exc_type, exc_value, exc_traceback)
            except Exception:
                logging.error("Error in getConnectionManageRefresh(): An error occured when trying to get users")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)

            #get task list
            try:
                #res = proxapi.nodes(nodename).tasks.get()
                res = proxapi.cluster.tasks.get()
                connected = {}
                for task in res:
                    if task['type'] != "vncproxy" or task['node'] != nodename:
                        continue
                    taskvmid = None
                    taskvmname = None
                    if 'id' in task:
                        taskvmid = task['id']
                        taskvmname = vmid_name[taskvmid]
                    else:
                        continue
                    taskuser = task['user']
                    taskstarttime = None
                    if 'starttime' in task:
                        taskstarttime = task['starttime']
                    taskendtime = 'Active'
                    if 'endtime' in task:
                        taskendtime = task['endtime']
                    if len(taskuser) > 4 and taskuser[-4:] == "@pam":
                        taskuser = task['user'][:-4]
                    if (taskuser, taskvmname) in connected:
                        #since these come from logs, there may be more than one connection. Take the later one.
                        if taskstarttime != None and (connected[(taskuser,taskvmname)]['taskendtime'] != "Active" and taskstarttime > connected[(taskuser,taskvmname)]['taskendtime']) or taskendtime == "Running":
                            connected[(taskuser, taskvmname)] = {"taskstarttime": taskstarttime, "taskendtime": taskendtime, "taskvmid": taskvmid}
                        #else, do nothing, leave the previous
                    else:
                        connected[(taskuser, taskvmname)] = {"taskstarttime": taskstarttime, "taskendtime": taskendtime, "taskvmid": taskvmid}
                            
            except Exception:
                logging.error("Error in getConnectionManageRefresh(): An error occured when trying to get users")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)

            for username in pools.keys():
                for vmname in pools[username]:
                    #if user/vmname is in connected, then user is connected
                    user_perm = "Found"
                    active = "No Record"
                    if (username, vmname) in connected:
                        if connected[(username, vmname)]['taskendtime'] != 'Active':
                            active = datetime.datetime.fromtimestamp(connected[(username, vmname)]['taskendtime']).strftime("%Y-%m-%d %H:%M:%S")
                        else:
                            active = 'Active'
                        
                    self.usersConnsStatus[(username,vmname)] = {"user_status": user_perm, "connStatus": active}
            
        except Exception as e:
            logging.error("Error in getConnectionManageRefresh(). Could not refresh connections!")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            trace_back = traceback.extract_tb(exc_traceback)
            traceback.print_exception(exc_type, exc_value, exc_traceback)
            return None
        finally:
            self.lock.release()

    def get_user_pass_frombase(self, base, num_users):
        logging.debug("get_user_pass_frombase(): instantiated")
        #not efficient at all, but it's a quick lazy way to do it:
        answer = []
        for i in range(1,num_users+1):
            answer.append(((str(base)+str(i),str(base)+str(i))))
        return answer

    def get_user_pass_fromfile(self, filename):
        logging.debug("get_user_pass_fromfile(): instantiated")
        #not efficient at all, but it's a quick lazy way to do it:
        answer = []
        i = 0
        try:
            if os.path.exists(filename) == False:
                logging.error("getConnectionManageStatus(): Filename: " + filename + " does not exists; returning")
                return None
            with open(filename) as infile:
                reader = csv.reader(infile, delimiter=" ")
                for user, password in reader:
                    i = i+1
                    answer.append((user, password))
            # if len(answer) < num_users:
            #     logging.error("getConnectionManageStatus(): file does not have enough users: " + len(answer) + "; returning")
            #     return None
            return answer
        except Exception as e:
            logging.error("Error in getConnectionManageStatus().")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            trace_back = traceback.extract_tb(exc_traceback)
            #traceback.print_exception(exc_type, exc_value, exc_traceback)
            return None
