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
        self.usersConnsStatus = {}
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
    def clearAllUsers(self, configname, keycloakHostname, username, password, exceptions=["root","admin", "jacosta", "jcacosta", "darien", "piplai"]):
        logging.debug("clearAllUsers(): instantiated")
        t = threading.Thread(target=self.runClearAllUsers, args=(configname, keycloakHostname, username, password, exceptions))
        self.writeStatus+=1
        t.start()
        return 0

    def runClearAllUsers(self, configname, keycloakHostname, musername, mpassword, exceptions=["root","admin", "jacosta", "jcacosta", "darien", "piplai"]):
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
        return {"readStatus" : self.readStatus, "writeStatus" : self.writeStatus, "usersStatus" : self.usersConnsStatus}
    
    def getUserManageRefresh(self, configname, proxHostname, musername, mpassword):
        logging.debug("getUserManageRefresh(): instantiated")
        try:
            self.lock.acquire()
            self.usersStatus.clear()

            vmserverip, vmserversshport, rdpbroker, chatserver, challengesserver, keycloakserver, creds_file = self.eco.getExperimentServerInfo(configname)
            
            userpool = UserPool()
            usersConns = userpool.generateUsersConns(configname, creds_file=creds_file)

            try:
                keycloakapi = self.getKeycloakAPI(configname, musername, mpassword)
                if keycloakapi == None:
                    return None

            except Exception:
                logging.error("Error in getUserManageRefresh(): An error occured when trying to connect to proxmox")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
                return None
            
            try:
                users = keycloakapi.get_users({})
                for user_info in users:
                    username = user_info['username']
                    userid = user_info['id']
                    if username not in self.usersStatus:
                        self.usersStatus[username] = {}
                    self.usersStatus[username]["user_status"] = "exists"
                    self.usersStatus[username]["connStatus"] = "inactive"
                    user_sessions = keycloakapi.get_sessions(userid)
                    print("User Sessions: " + str(user_sessions))
                    if user_sessions != None and user_sessions != []:
                        #get info about user
                        self.usersStatus[username]["user_status"] = "active"
                        lastAccess = user_sessions[0]['lastAccess']
                        formatted_time = datetime.datetime.fromtimestamp(lastAccess / 1000).strftime('%Y-%m-%d %H:%M:%S')
                        self.usersStatus[username]["connStatus"] = formatted_time
                    else:
                        self.usersStatus[username]["user_status"] = "exists"
                        self.usersStatus[username]["connStatus"] = "inactive"

            except Exception:
                logging.error("Error in getConnectionManageRefresh: An error occured when trying to get users")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
                self.usersConnsStatus = {}
                return None
            
            for (username, password) in usersConns:
                for conn in usersConns[(username, password)]:
                    cloneVMName = conn[0]
                    if username in self.usersStatus:
                        self.usersConnsStatus[(username,cloneVMName)] = {"user_status": self.usersStatus[username]["user_status"], "connStatus": self.usersStatus[username]["connStatus"]}

            logging.debug("getConnectionManageRefresh(): usersStatus: " + str(self.usersStatus))

        except Exception as e:
            logging.error("Error in getConnectionManageRefresh(). Could not refresh connections!")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            trace_back = traceback.extract_tb(exc_traceback)
            traceback.print_exception(exc_type, exc_value, exc_traceback)
            self.usersConnsStatus = {}
            return None
        finally:
            self.lock.release()