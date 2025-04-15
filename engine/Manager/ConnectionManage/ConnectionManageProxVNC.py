import logging
import sys, traceback
import threading
import shlex
import os
import csv
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
        if username != None and password != None and username.strip() != "" and password.strip() != "" and len(username) > 4:
            self.setRemoteCreds(username, password)
        self.setRemoteCreds(username, password)

    def setRemoteCreds(self, username=None, password=None):
        logging.info("ProxmoxManage.setRemoteCreds(): Initializing ProxmoxManage; collecting VM information...")
        if username != None and password != None and username.strip() != "" and password.strip() != "" and len(username) > 4:
            self.proxapi = self.getProxAPI(username=username, password=password)
            sshuser = username[:-4]
            self.proxssh = self.getProxSSH(username=sshuser, password=password)
        logging.info("ProxmoxManage.setRemoteCreds(): Done...")

    def getProxAPI(self, username=None, password=None):
        logging.debug("ProxmoxManage: getProxAPI(): instantiated")
        try:
            server = self.s.getConfig()['PROXMOX']['VMANAGE_SERVER']
            port = self.s.getConfig()['PROXMOX']['VMANAGE_APIPORT']
            if self.proxapi == None and username != None and password != None and username.strip() != "" and password.strip() != "":
                self.proxapi = ProxmoxAPI(server, port=port, user=username, password=password, verify_ssl=False)
            elif self.proxapi != None and username != None and password != None and username.strip() != "" and password.strip() != "":
                self.proxapi = None
                self.proxapi = ProxmoxAPI(server, port=port, user=username, password=password, verify_ssl=False)
            return self.proxapi
        except Exception:
            logging.error("Error in getProxAPI(): An error occured when trying to connect to proxmox")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
            self.proxapi = None
            return None
        
    def getProxSSH(self, username=None, password=None):
        logging.debug("ProxmoxManage: getProxSSH(): instantiated")
        try:
            server = self.s.getConfig()['PROXMOX']['VMANAGE_SERVER']
            port = self.s.getConfig()['PROXMOX']['VMANAGE_CMDPORT']
            if self.proxssh == None and username != None and password != None and username.strip() != "" and password.strip() != "":
                self.proxssh = ssh_paramiko.SshParamikoSession(server,port=port, user=username,password=password)
            elif self.proxssh != None and username != None and password != None and username.strip() != "" and password.strip() != "":
                self.proxssh = None
                self.proxssh = ssh_paramiko.SshParamikoSession(server,port=port, user=username,password=password)
            return self.proxssh
        except Exception:
            logging.error("Error in getProxSSH(): An error occured when trying to connect to proxmox with ssh")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
            self.proxssh = None
            return None

    def basic_blocking_task_status(self, proxmox_api, task_id, caller=""):
        logging.debug("ProxmoxManage: basic_blocking_task_status(): instantiated by " + str(caller))
        Tasks.blocking_status(proxmox_api, task_id)

    #abstractmethod
    def createConnections(self, configname, proxHostname, username, password, url_path, method, maxConnections="", maxConnectionsPerUser="", width="", height="", bitdepth="", creds_file="", itype="", name=""):
        logging.debug("createConnections(): instantiated")
        t = threading.Thread(target=self.runCreateConnections, args=(configname, proxHostname, username, password, url_path, method, maxConnections, maxConnectionsPerUser, width, height, bitdepth, creds_file, itype, name))
        self.writeStatus+=1
        t.start()
        return 0

    def runCreateConnections(self, configname, proxHostname, musername, mpassword, url_path, method, maxConnections="", maxConnectionsPerUser="", width="", height="", bitdepth="", creds_file="", itype="", name=""):
        logging.debug("runCreateConnections(): instantiated")
        #call guac backend API to make connections as specified in config file and then set the complete status
        rolledoutjson = self.eco.getExperimentVMRolledOut(configname)
        validconnsnames = self.eco.getValidVMsFromTypeName(configname, itype, name, rolledoutjson)

        userpool = UserPool()
        usersConns = userpool.generateUsersConns(configname, creds_file=creds_file)

        try:
            logging.debug("runCreateConnection(): proxHostname: " + str(proxHostname) + " username/pass: " + musername + " url_path: " + url_path + " method: " + str(method) + " creds_file: " + creds_file)
            
            #get accessors to the proxmox api and ssh
            try:
                nodename = self.s.getConfig()['PROXMOX']['VMANAGE_NODE_NAME']
                proxapi = self.getProxAPI(musername, mpassword)
                if proxapi == None:
                    return None

                if musername != None and len(musername) > 4 and mpassword != None and musername.strip() != "" and mpassword.strip() != "":
                    sshuser = musername[:-4]
                    proxssh = self.getProxSSH(username=sshuser,password=mpassword)
                else:
                    proxssh = self.getProxSSH(musername, mpassword)
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
                            if username not in users and username not in created_users_lin:
                                logging.debug( "Creating User: " + username)
                                try:
                                    result = self.proxssh._exec(shlex.split("/usr/sbin/useradd " + username))
                                    if result != None and  len(result) > 1 and "already exists" in result[1]:
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
                                    if result != None and len(result) > 1 and "already exists" in result[1]:
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
    def clearAllConnections(self, proxHostname, username, password, url_path, method, exceptions=[]):
        logging.debug("clearAllConnections(): instantiated")
        t = threading.Thread(target=self.runClearAllConnections, args=(proxHostname, username, password, url_path, method, exceptions))
        self.writeStatus+=1
        t.start()
        return 0

    def runClearAllConnections(self, proxHostname, musername, mpassword, url_path, method, exceptions=["root","nathanvms", "ana", "arodriguez", "jacosta"]):
        logging.debug("runClearAllConnections(): instantiated")
        try:
            logging.debug("runClearAllConnections(): proxHostname: " + str(proxHostname) + " username/pass: " + musername + " url_path: " + url_path + " method: " + str(method))
            
            #get accessors to the proxmox api and ssh
            try:
                nodename = self.s.getConfig()['PROXMOX']['VMANAGE_NODE_NAME']
                proxapi = self.getProxAPI(musername, mpassword)
                if proxapi == None:
                    return None

                if musername != None and len(musername) > 4 and mpassword != None and musername.strip() != "" and mpassword.strip() != "":
                    sshuser = musername[:-4]
                    proxssh = self.getProxSSH(username=sshuser,password=mpassword)
                else:
                    proxssh = self.getProxSSH(musername, mpassword)
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
                    logging.warning("runClearAllConnections(): Pool " + pool + " already exists, skipping.")
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
                    result = proxssh._exec(shlex.split("userdel " + user))
                    if result != None and  len(result) > 1 and "does not exist" in result[1]:
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
                    if result != None and  len(result) > 1 and "does not exist" in result[1]:
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
        finally:
            self.writeStatus-=1

    #abstractmethod
    def removeConnections(self, configname, proxHostname, username, password, url_path, method, creds_file="", itype="", name=""):
        logging.debug("removeConnections(): instantiated")
        t = threading.Thread(target=self.runRemoveConnections, args=(configname,proxHostname, username, password, url_path, method, creds_file, itype, name))
        self.writeStatus+=1
        t.start()
        return 0

    def runRemoveConnections(self, configname, proxHostname, musername, mpassword, url_path, method, creds_file, itype, name):
        logging.debug("runRemoveConnections(): instantiated")
        try:
            logging.debug("runRemoveConnections(): proxHostname: " + str(proxHostname) + " username/pass: " + musername + " url_path: " + url_path + " method: " + str(method))
            rolledoutjson = self.eco.getExperimentVMRolledOut(configname)
            validconnsnames = self.eco.getValidVMsFromTypeName(configname, itype, name, rolledoutjson)

            userpool = UserPool()
            usersConns = userpool.generateUsersConns(configname, creds_file=creds_file)

            #get accessors to the proxmox api and ssh
            try:
                nodename = self.s.getConfig()['PROXMOX']['VMANAGE_NODE_NAME']
                proxapi = self.getProxAPI(musername, mpassword)
                if proxapi == None:
                    return None

                if musername != None and len(musername) > 4 and mpassword != None and musername.strip() != "" and mpassword.strip() != "":
                    sshuser = musername[:-4]
                    proxssh = self.getProxSSH(username=sshuser,password=mpassword)
                else:
                    proxssh = self.getProxSSH(musername, mpassword)
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
                if pool not in validconnsnames and pool == "nathanvms" or pool == "ana" or pool in pools_removed:
                    continue
                try:
                    members_ds = proxapi.pools(pool).get()
                    members = []
                    for member in members_ds['members']:
                        members.append(str(member['vmid']))
                except ResourceException:
                    logging.warning("runClearAllConnections(): Pool " + pool + " already exists, skipping.")
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
                    pools_removed.append(pool)
                except ResourceException:
                    logging.warning("runClearAllConnections(): Pool " + pool + " already exists, skipping.")
                    # exc_type, exc_value, exc_traceback = sys.exc_info()
                    # traceback.print_exception(exc_type, exc_value, exc_traceback)                                    
                except Exception:
                    logging.error("runClearAllConnections(): error when trying to remove pool: " + pool)
                    # exc_type, exc_value, exc_traceback = sys.exc_info()
                    # traceback.print_exception(exc_type, exc_value, exc_traceback)

            #remove users 
            for user in users:
                if user or user in users_removed_lin:
                    continue
                logging.debug( "Removing User: " + user)
                try:
                    result = proxssh._exec(shlex.split("userdel " + user))
                    if result != None and  len(result) > 1 and "does not exist" in result[1]:
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
                    if result != None and  len(result) > 1 and "does not exist" in result[1]:
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
    
    def getConnectionManageRefresh(self, proxHostname, username, password, url_path, method):
        logging.debug("getConnectionManageStatus(): instantiated")
        try:
            self.lock.acquire()
            self.usersConnsStatus.clear()
            proxConn = Guacamole(proxHostname,username=username,password=password,url_path=url_path,method=method)
            #username, connName/VMName, userStatus (admin/etc.), connStatus (connected/not)
            users = proxConn.get_users()
            
            connIDsNames = {}
            activeConns = {}
            allConnections = proxConn.get_connections()
            if 'childConnections' in allConnections:
                for conn in proxConn.get_connections()['childConnections']:
                    connIDsNames[conn['identifier']] = conn['name']
            guac_activeConns = proxConn.get_active_connections()
            for conn in guac_activeConns:
                activeConns[(guac_activeConns[conn]["username"], guac_activeConns[conn]["connectionIdentifier"])] = True

            for user in users:
                #user status first
                perm = proxConn.get_permissions(user)
                user_perm = "not_found"
                if "READ" in perm['userPermissions'][user]:
                    user_perm = "Non-Admin"
                if "ADMINISTER" in perm['userPermissions'][user]:
                    user_perm = "Admin"
                #next, get the list of connections and the names of those connections and their status associated with those connections            
                for connID in perm['connectionPermissions']:
                    active = "not_connected"
                    #if the connection is in an active state (exists in our activeConns dict), then state it as such
                    if (user, connID) in activeConns:
                        active = "connected"
                    self.usersConnsStatus[(user, connIDsNames[connID])] = {"user_status": user_perm, "connStatus": active}
            
        except Exception as e:
            logging.error("Error in getConnectionManageStatus(). Did not remove connection or relation!")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            trace_back = traceback.extract_tb(exc_traceback)
            #traceback.print_exception(exc_type, exc_value, exc_traceback)
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
