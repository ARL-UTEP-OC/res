import logging
import sys, traceback
import threading
import os
import csv
import time
import datetime
from engine.Manager.ConnectionManage.ConnectionManage import ConnectionManage
from keycloak import KeycloakAdmin
from keycloak import KeycloakOpenIDConnection
from engine.Configuration.ExperimentConfigIO import ExperimentConfigIO
from engine.Configuration.SystemConfigIO import SystemConfigIO
from engine.Configuration.UserPool import UserPool
from threading import RLock

class ConnectionManageKeycloakSSO(ConnectionManage):
    def __init__(self, username=None, password=None):
        logging.debug("ConnectionManageKeycloakSSO(): instantiated")
        ConnectionManage.__init__(self)
        self.keycloakapi = None
        self.eco = ExperimentConfigIO.getInstance()
        self.usersStatus = {}
        self.lock = RLock()
        self.s = SystemConfigIO()

    def getKeycloakAPI(self, configname, username=None, password=None):
        logging.debug("Keycloak: getProxAPI(): instantiated")
        try:
            vmHostname, vmserversshport, rdiplayhostname, chatserver, challengesserver, keycloakserver, users_file = self.eco.getExperimentServerInfo(configname)
            splithostname = keycloakserver.split("://")
            if len(splithostname) > 1:
                rsplit = splithostname[1]
                if len(rsplit.split(":")) > 1:
                    port = rsplit.split(":")[1].split("/")[0]
                server = rsplit.split("/")[0]

            keycloak_connection = KeycloakAdmin(server_url=keycloakserver,
                                username=username,
                                password=password,
                                verify=True)
            return keycloak_connection

        except Exception:
            logging.error("Error in getProxAPI(): An error occured when trying to connect to Keycloak; possibly incorrect credentials.")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
            self.proxapi = None
            return None

    def deleteUsers(self, configname, keycloakHostname, username, password, creds_file="", itype="", name="", exceptions=[]):
        logging.debug("deleteUsers(): instantiated")
        t = threading.Thread(target=self.runDeleteUsers, args=(configname, keycloakHostname, username, password, creds_file, itype, name, exceptions))
        self.writeStatus+=1
        t.start()
        return 0

    def runDeleteUsers(self, configname, keycloakHostname, musername, mpassword, creds_file="", itype="", name="", exceptions=["root","admin", "jacosta", "jcacosta"]):
        logging.debug("runDeleteUsers(): instantiated")
        #call keycloak backend API to make connections as specified in config file and then set the complete status
        rolledoutjson = self.eco.getExperimentVMRolledOut(configname)
        validconnsnames = self.eco.getValidVMsFromTypeName(configname, itype, name, rolledoutjson)

        userpool = UserPool()
        usersConns = userpool.generateUsersConns(configname, creds_file=creds_file)
        users = []
        try:
            #get accessors to the proxmox api and ssh
            try:
                keycloakAPI = self.getKeycloakAPI(configname, musername, mpassword)
                if keycloakAPI == None:
                    return None

            except Exception:
                logging.error("Error in runDeleteUsers(): An error occured when trying to connect to proxmox")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
                return None
            #get the list of all users and pools
            try:
                res = keycloakAPI.get_users({})
                for user_info in res:
                    users.append(user_info['username'])
            except Exception:
                logging.error("Error in runDeleteUsers(): An error occured when trying to get users")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)

            try:
                for (username, password) in usersConns:  
                    for conn in usersConns[(username, password)]:
                        cloneVMName = conn[0]

                        #only if this is a specific connection to create; based on itype and name
                        if cloneVMName in validconnsnames:
                            if users != None and username not in users and username in exceptions:
                                logging.debug("runDeleteUsers(): User " + username + " does not exist; skipping...")
                                continue             
                            logging.debug("Getting Username ID: " + username)
                            userid = keycloakAPI.get_user_id(username)
                            if userid == None:
                                logging.debug("runDeleteUsers(): User " + username + " does not exist; skipping...")
                                continue
                            # Delete user
                            logging.debug("-User ID: " + str(userid))
                            logging.info("runDeleteUsers(): Removing user: " + username + " ID: " + str(userid))
                            result = keycloakAPI.delete_user(userid)

                            if result == {}:
                                logging.debug("runDeleteUsers(): User removed: " + str(result))
                                if username in users:
                                    users.remove(username)
                            else:
                                logging.debug("runDeleteUsers(): User " + username + " could not be deleted...")
            except Exception:
                    logging.error("runDeleteUsers(): (): Error in runDeleteUsers(): when trying to remove user.")
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    traceback.print_exception(exc_type, exc_value, exc_traceback)
            logging.debug("runDeleteUsers(): (): Complete...")
        except Exception:
            logging.error("runDeleteUsers(): (): Error in runDeleteUsers(): (): An error occured ")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
        finally:
            self.writeStatus-=1

    #abstractmethod
    def createUsers(self, configname, keycloakHostname, username, password, creds_file="", itype="", name=""):
        logging.debug("createConnections(): instantiated")
        t = threading.Thread(target=self.runCreateUsers, args=(configname, keycloakHostname, username, password, creds_file, itype, name))
        self.writeStatus+=1
        t.start()
        return 0

    def runCreateUsers(self, configname, keycloakHostname, musername, mpassword, creds_file="", itype="", name=""):
        logging.debug("runCreateUsers(): instantiated")
        #call keycloak backend API to make connections as specified in config file and then set the complete status
        rolledoutjson = self.eco.getExperimentVMRolledOut(configname)
        validconnsnames = self.eco.getValidVMsFromTypeName(configname, itype, name, rolledoutjson)

        userpool = UserPool()
        usersConns = userpool.generateUsersConns(configname, creds_file=creds_file)
        users = []
        try:
            #get accessors to the proxmox api and ssh
            try:
                keycloakAPI = self.getKeycloakAPI(configname, musername, mpassword)
                if keycloakAPI == None:
                    return None

            except Exception:
                logging.error("Error in runCreateUsers(): An error occured when trying to connect to proxmox")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
                return None
            #get the list of all users and pools
            try:
                res = keycloakAPI.get_users({})
                for user_info in res:
                    users.append(user_info['username'])
            except Exception:
                logging.error("Error in runCreateUsers(): An error occured when trying to get users")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)

            try:
                for (username, password) in usersConns:  
                    for conn in usersConns[(username, password)]:
                        cloneVMName = conn[0]

                        #only if this is a specific connection to create; based on itype and name
                        if cloneVMName in validconnsnames:
                            if users != None and username in users:
                                logging.debug("runCreateUsers(): User " + username + " already exists; skipping...")
                                continue             
                            logging.info("runCreateUsers(): Creating user: " + username)
                            email = username+str("@fake.com")
                            result = keycloakAPI.create_user({"email": email,
                                "username": username,
                                "enabled": True,
                                "firstName": username,
                                "lastName": username,
                                "credentials": [{"value": password, "type": "password",}]},
                                exist_ok=True)

                            if result != {}:
                                logging.debug("runCreateUsers(): User create with ID: " + str(result))
                                users.append(username)
                            else:
                                logging.debug("runCreateUsers(): User " + username + " could not be created...")
            except Exception:
                    logging.error("runCreateUsers(): (): Error in runCreateUsers(): when trying to add user.")
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    traceback.print_exception(exc_type, exc_value, exc_traceback)
            logging.debug("runCreateUsers(): (): Complete...")
        except Exception:
            logging.error("runCreateUsers(): (): Error in runCreateUsers(): (): An error occured ")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
        finally:
            self.writeStatus-=1

    #abstractmethod
    def clearAllUsers(self, configname, keycloakHostname, username, password, exceptions=["root","admin", "jacosta", "jcacosta"]):
        logging.debug("clearAllUsers(): instantiated")
        t = threading.Thread(target=self.runClearAllUsers, args=(configname, keycloakHostname, username, password, exceptions))
        self.writeStatus+=1
        t.start()
        return 0

    def runClearAllUsers(self, configname, keycloakHostname, musername, mpassword, exceptions=["root","admin", "jacosta", "jcacosta"]):
        logging.debug("runDeleteUsers(): instantiated")
        #call keycloak backend API to make connections as specified in config file and then set the complete status
        users = []
        try:
            #get accessors to the api
            try:
                keycloakAPI = self.getKeycloakAPI(configname, musername, mpassword)
                if keycloakAPI == None:
                    return None

            except Exception:
                logging.error("Error in runDeleteUsers(): An error occured when trying to connect to proxmox")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
                return None
            #get the list of all users
            try:
                res = keycloakAPI.get_users({})
                for user_info in res:
                    users.append(user_info['username'])
            except Exception:
                logging.error("Error in runDeleteUsers(): An error occured when trying to get users")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
                return None
            removed = []
            try:
                for username in users:
                    #remove the user
                    if username in removed or username in exceptions:
                        logging.debug("runDeleteUsers(): User " + username + " already removed or in exceptions list...")
                        continue             
                    logging.info("runDeleteUsers(): Removing user: " + username)
                    logging.debug("Getting Username ID: " + username)
                    userid = keycloakAPI.get_user_id(username)
                    if userid == None:
                        return False
                    # Delete user
                    logging.debug("-User ID: " + str(userid))
                    result = keycloakAPI.delete_user(userid)

                    if result != {}:
                        logging.debug("runDeleteUsers(): User removed: " + str(result))
                        if username in users:
                            removed.append(username)
                    else:
                        logging.debug("runDeleteUsers(): User " + username + " could not be deleted...")
            except Exception:
                    logging.error("runDeleteUsers(): (): Error in runDeleteUsers(): when trying to remove user.")
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    traceback.print_exception(exc_type, exc_value, exc_traceback)
            logging.debug("runDeleteUsers(): (): Complete...")
        except Exception:
            logging.error("runDeleteUsers(): (): Error in runDeleteUsers(): (): An error occured ")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
        finally:
            self.writeStatus-=1

    #abstractmethod
    def getUserManageStatus(self):
        logging.debug("getUserManageStatus(): instantiated")
        return {"readStatus" : self.readStatus, "writeStatus" : self.writeStatus, "usersStatus" : self.usersStatus}
    
    def getUserManageRefresh(self, configname, proxHostname, musername, mpassword):
        logging.debug("getUserManageRefresh(): instantiated")
        try:
            self.lock.acquire()
            self.usersStatus.clear()

            # if pool name with username exists, then "connection exists"
            # check tasks and look for those without end time; if type is vnxproxy, get username; that user is connected
            try:
                keycloakapi = self.getKeycloakAPI(configname, musername, mpassword)
                if keycloakapi == None:
                    return None

            except Exception:
                logging.error("Error in getUserManageRefresh(): An error occured when trying to connect to proxmox")
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
                        logging.warning("getConnectionManageRefresh(): Pool " + pool_id + " does not exist, skipping.")
                        # exc_type, exc_value, exc_traceback = sys.exc_info()
                        # traceback.print_exception(exc_type, exc_value, exc_traceback)                                    
                    except Exception:
                        logging.error("getConnectionManageRefresh(): error when trying to remove pool: " + pool_id)
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
                logging.debug("getConnectionManageRefresh(): username: " + username)
                if username not in pools or pools[username] == []:
                    #if user is not in pools, then user is not connected
                    user_perm = "Found"
                    active = "Empty Pool"
                    self.usersStatus[(username,"")] = {"user_status": user_perm, "connStatus": active}
                    continue
                for vmname in pools[username]:
                    #if user/vmname is in connected, then user is connected
                    active = "No Recent Record"
                    if (username, vmname) in connected:
                        if connected[(username, vmname)]['taskendtime'] != 'Active':
                            active = datetime.datetime.fromtimestamp(connected[(username, vmname)]['taskendtime']).strftime("%Y-%m-%d %H:%M:%S")
                        else:
                            active = 'Active'
                    logging.debug("getConnectionManageRefresh(): username: " + username + "; vmname: " + vmname + "; active: " + str(active))
                    self.usersStatus[(username,vmname)] = {"user_status": user_perm, "connStatus": active}
            logging.debug("getConnectionManageRefresh(): usersStatus: " + str(self.usersStatus))
            
        except Exception as e:
            logging.error("Error in getConnectionManageRefresh(). Could not refresh connections!")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            trace_back = traceback.extract_tb(exc_traceback)
            traceback.print_exception(exc_type, exc_value, exc_traceback)
            return None
        finally:
            self.lock.release()
            self.writeStatus-=1