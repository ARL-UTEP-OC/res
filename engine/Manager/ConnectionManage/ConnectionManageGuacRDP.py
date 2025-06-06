import logging
import sys, traceback
import threading
import json
import os
import csv
from engine.Manager.ConnectionManage.ConnectionManage import ConnectionManage
from engine.ExternalIFX.GuacIFX import GuacIFX
from engine.Configuration.ExperimentConfigIO import ExperimentConfigIO
from engine.Configuration.SystemConfigIO import SystemConfigIO
from engine.Configuration.UserPool import UserPool
from guacapy import Guacamole
from threading import RLock

class ConnectionManageGuacRDP(ConnectionManage):
    def __init__(self):
        logging.debug("ConnectionManageGuacRDP(): instantiated")
        ConnectionManage.__init__(self)
        self.guacifx = GuacIFX()
        self.eco = ExperimentConfigIO.getInstance()
        self.usersConnsStatus = {}
        self.lock = RLock()

    #abstractmethod
    def createConnections(self, configname, guacHostname, username, password, maxConnections="", maxConnectionsPerUser="", width="1400", height="1050", bitdepth="16", creds_file="", itype="", name=""):
        logging.debug("createConnections(): instantiated")
        t = threading.Thread(target=self.runCreateConnections, args=(configname, guacHostname, username, password, maxConnections, maxConnectionsPerUser, width, height, bitdepth, creds_file, itype, name))
        t.start()
        return 0

    def runCreateConnections(self, configname, guacHostname, musername, mpassword, maxConnections, maxConnectionsPerUser, width, height, bitdepth, creds_file, itype, name):
        logging.debug("runCreateConnections(): instantiated")
        #call guac backend API to make connections as specified in config file and then set the complete status
        rolledoutjson = self.eco.getExperimentVMRolledOut(configname)
        validconnsnames = self.eco.getValidVMsFromTypeName(configname, itype, name, rolledoutjson)
        # if creds_file == None or creds_file == "":
        #     creds_file = self.eco.getExperimentConfigFile(configname)

        userpool = UserPool()
        usersConns = userpool.generateUsersConns(configname, creds_file=creds_file)

        try:
            if guacHostname == None or guacHostname == "":
                vmserver, vmserversshport, guacHostname, chatserver, challengesserver, users_file = self.eco.getExperimentServerInfo(configname)
                if guacHostname == None or guacHostname == "":
                    logging.error("runCreateConnections(): Guacamole Hostname not found; returning")
                    return -1
            self.writeStatus = ConnectionManage.CONNECTION_MANAGE_CREATING
            url_path = "/"
            if guacHostname.startswith("http://"):
                guacConnMethod = 'http'
            elif guacHostname.startswith("https://"):
                guacConnMethod = 'https'
            else:
                #if guacHostname doesn't start with http(s), then we need to add it
                guacHostname = "https://" + guacHostname
                guacConnMethod = 'https'

            if len(guacHostname.split("://")) > 1:
                tmp_path = guacHostname.split("://")[1]
                url_path = "".join(tmp_path.split("/")[1:])
                if url_path.startswith("/") == False:
                    url_path = "/" + url_path
                if url_path.endswith("/") == False:
                    url_path = url_path + "/"
            guacHostname = guacHostname.split("://")[1].split('/')[0]
            guacConn = Guacamole(guacHostname,username=musername,password=mpassword,url_path=url_path, method=guacConnMethod)
            if guacConn == None:
                logging.error("runCreateConnection(): Error with guac connection... skipping: " + str(guacHostname) + " " + str(musername))
                self.writeStatus = ConnectionManage.CONNECTION_MANAGE_COMPLETE
                return -1
            user_dict = guacConn.get_users()
            created_users = []
            try:
                for (username, password) in usersConns:
                    for conn in usersConns[(username, password)]:
                        cloneVMName = conn[0]
                        vmServerIP = conn[1]
                        vrdpPort = conn[2]
                        #only if this is a specific connection to create; based on itype and name
                        if cloneVMName in validconnsnames:
                            #if user doesn't exist, create it
                            if username not in user_dict and username not in created_users:
                                logging.debug( "Creating User: " + username)
                                try:
                                    result = self.createUser(guacConn, username, password)
                                    if result == "already_exists":
                                        logging.debug("User already exists; skipping...")
                                    else:
                                        created_users.append(username)
                                        logging.debug("User Created: " + str(result))
                                except Exception:
                                    logging.error("runCreateConnections(): Error in runCreateConnections(): when trying to add user.")
                                    exc_type, exc_value, exc_traceback = sys.exc_info()
                                    traceback.print_exception(exc_type, exc_value, exc_traceback)
                            #add the connection association
                            result = self.createConnAssociation(guacConn, cloneVMName, username, vmServerIP, vrdpPort, maxConnections, maxConnectionsPerUser, width, height, bitdepth)
                            if result == "already_exists":
                                logging.debug("Connection already exists; skipping...")
            except Exception:
                    logging.error("runCreateConnections(): Error in runCreateConnections(): when trying to add connection.")
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    traceback.print_exception(exc_type, exc_value, exc_traceback)
            logging.debug("runCreateConnections(): Complete...")
            self.writeStatus = ConnectionManage.CONNECTION_MANAGE_COMPLETE
        except Exception:
            logging.error("runCreateConnections(): Error in runCreateConnections(): An error occured ")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
            self.writeStatus = ConnectionManage.CONNECTION_MANAGE_COMPLETE
            return
        finally:
            self.writeStatus = ConnectionManage.CONNECTION_MANAGE_COMPLETE

    #abstractmethod
    def clearAllConnections(self, configname, guacHostname, username, password):
        logging.debug("clearAllConnections(): instantiated")
        t = threading.Thread(target=self.runClearAllConnections, args=(configname, guacHostname, username, password))
        t.start()
        return 0

    def runClearAllConnections(self, guacHostname, username, password):
        self.writeStatus = ConnectionManage.CONNECTION_MANAGE_REMOVING

        url_path = "/"
        if guacHostname.startswith("http://"):
            guacConnMethod = 'http'
        elif guacHostname.startswith("https://"):
            guacConnMethod = 'https'
        else:
            #if guacHostname doesn't start with http(s), then we need to add it
            guacHostname = "https://" + guacHostname
            guacConnMethod = 'https'

        if len(guacHostname.split("://")) > 1:
            tmp_path = guacHostname.split("://")[1]
            url_path = "".join(tmp_path.split("/")[1:])
            if url_path.startswith("/") == False:
                url_path = "/" + url_path
            if url_path.endswith("/") == False:
                url_path = url_path + "/"            
        guacHostname = guacHostname.split("://")[1].split('/')[0]
        guacConn = Guacamole(guacHostname,username=username,password=password,url_path=url_path, method=guacConnMethod)
        if guacConn == None:
            logging.error("Error with guac connection... skipping: " + str(guacHostname) + " " + str(username))
            self.writeStatus = ConnectionManage.CONNECTION_MANAGE_COMPLETE
            return -1

        # Get list of all users
        usernames = guacConn.get_users()
        for username in usernames:
            logging.info( "Removing Username: " + username)
            try:
                guacConn.delete_user(username)
            except Exception:
                logging.error("runClearAllConnections(): Error in runClearAllConnections(): when trying to remove user.")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                #traceback.print_exception(exc_type, exc_value, exc_traceback)
        # Clear AllConnections
        connections = guacConn.get_connections()
        logging.debug( "Retrieved Connections: " + str(connections))
        if "childConnections" in connections:
            for connection in connections["childConnections"]:
                logging.info( "Removing Connection: " + str(connection))
                try:
                    guacConn.delete_connection(connection["identifier"])
                except Exception:
                        logging.error("runClearAllConnections(): Error in runClearAllConnections(): when trying to remove connection.")
                        exc_type, exc_value, exc_traceback = sys.exc_info()
                        #traceback.print_exception(exc_type, exc_value, exc_traceback)
        self.writeStatus = ConnectionManage.CONNECTION_MANAGE_COMPLETE

    #abstractmethod
    def removeConnections(self, configname, guacHostname, username, password, creds_file="", itype="", name=""):
        logging.debug("removeConnections(): instantiated")
        t = threading.Thread(target=self.runRemoveConnections, args=(configname,guacHostname, username, password, creds_file, itype, name))
        t.start()
        return 0

    def runRemoveConnections(self, configname, guacHostname, username, password, creds_file, itype, name):
        self.writeStatus = ConnectionManage.CONNECTION_MANAGE_REMOVING
        logging.debug("runRemoveConnections(): instantiated")
        #call guac backend API to remove connections as specified in config file and then set the complete status
        rolledoutjson = self.eco.getExperimentVMRolledOut(configname)
        validconnsnames = self.eco.getValidVMsFromTypeName(configname, itype, name, rolledoutjson)

        userpool = UserPool()
        try:
            usersConns = userpool.generateUsersConns(configname, creds_file=creds_file)
            self.writeStatus = ConnectionManage.CONNECTION_MANAGE_CREATING
            url_path = "/"
            if guacHostname.startswith("http://"):
                guacConnMethod = 'http'
            elif guacHostname.startswith("https://"):
                guacConnMethod = 'https'
            else:
                #if guacHostname doesn't start with http(s), then we need to add it
                guacHostname = "https://" + guacHostname
                guacConnMethod = 'https'

            if len(guacHostname.split("://")) > 1:
                tmp_path = guacHostname.split("://")[1]
                url_path = "".join(tmp_path.split("/")[1:])
                if url_path.startswith("/") == False:
                    url_path = "/" + url_path
                if url_path.endswith("/") == False:
                    url_path = url_path + "/"
            guacHostname = guacHostname.split("://")[1].split('/')[0]
            guacConn = Guacamole(guacHostname,username=username,password=password,url_path=url_path, method=guacConnMethod)
            if guacConn == None:
                logging.error("runRemoveConnections(): Error with guac connection... skipping: " + str(guacHostname) + " " + str(username))
                self.writeStatus = ConnectionManage.CONNECTION_MANAGE_COMPLETE
                return -1

            for (username, password) in usersConns:
                logging.debug( "Removing Connection for Username: " + username)
                try:
                    for conn in usersConns[(username, password)]:
                        cloneVMName = conn[0]
                        if cloneVMName in validconnsnames:
                            result = self.removeConnAssociation(guacConn, cloneVMName)
                            if result == "Does not Exist":
                                logging.debug("Connection doesn't exists; skipping...")

                    #check if any other connections exist for user, if not, remove the user too
                    try:
                        result = guacConn.get_permissions(username)
                        if len(result["connectionPermissions"]) == 0:
                            logging.debug( "Removing User: " + username)
                            result = self.removeUser(guacConn, username)
                            if result == "Does not Exist":
                                logging.debug("User doesn't exist; skipping...")
                    except Exception:
                        logging.error("runRemoveConnections(): Error in runRemoveConnections(): when trying to remove user.")
                        exc_type, exc_value, exc_traceback = sys.exc_info()
                        traceback.print_exception(exc_type, exc_value, exc_traceback)

                except Exception:
                        logging.error("runRemoveConnections(): Error in runRemoveConnections(): when trying to remove connection.")
                        exc_type, exc_value, exc_traceback = sys.exc_info()
                        traceback.print_exception(exc_type, exc_value, exc_traceback)
            logging.debug("runRemoveConnections(): Complete...")
            self.writeStatus = ConnectionManage.CONNECTION_MANAGE_COMPLETE
        except Exception:
            logging.error("runRemoveConnections(): Error in runRemoveConnections(): An error occured ")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
            self.writeStatus = ConnectionManage.CONNECTION_MANAGE_COMPLETE
            return
        finally:
            self.writeStatus = ConnectionManage.CONNECTION_MANAGE_COMPLETE

    #abstractmethod
    def openConnection(self, configname, experimentid, vmid):
        logging.debug("openConnection(): instantiated")
        t = threading.Thread(target=self.runOpenConnection, args=(configname,))
        t.start()
        return 0

    def runOpenConnection(self, configname, experimentid, vmid):
        logging.debug("runOpenConnection(): instantiated")
        self.writeStatus = ConnectionManage.CONNECTION_MANAGE_OPENING
        #open an RDP session using configuration from systemconfigIO to the specified experimentid/vmid
        self.writeStatus = ConnectionManage.CONNECTION_MANAGE_COMPLETE

    def createUser(self, guacConn, username, password):
        logging.debug("createUser(): Instantiated")
        try:
            ########User creation##########
            userCreatePayload = {"username":username, "password":password, "attributes":{ "disabled":"", "expired":"", "access-window-start":"", "access-window-end":"", "valid-from":"", "valid-until":"", "timezone":0}}
            result = guacConn.add_user(userCreatePayload)
            return result
        except Exception as e:
            logging.error("Error in createUser().")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            # Extract unformatter stack traces as tuples
            trace_back = traceback.extract_tb(exc_traceback)
            #traceback.print_exception(exc_type, exc_value, exc_traceback)
            return None

    def removeUser(self, guacConn, username):
        logging.debug("removeUser(): Instantiated")
        try:
            ########User removal##########
            result = guacConn.delete_user(username)
            return result
        except Exception as e:
            logging.error("Error in removeUser().")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            # Extract unformatter stack traces as tuples
            trace_back = traceback.extract_tb(exc_traceback)
            #traceback.print_exception(exc_type, exc_value, exc_traceback)
            return None

    def createConnAssociation(self, guacConn, connName, username, ip, port, maxConnections, maxConnectionsPerUser, width, height, bitdepth):
        logging.debug("createConnAssociation(): Instantiated")
        try:
            #logic to add a user/connection and associate them together
            ########Connection creation##########
            s = SystemConfigIO()
            protocol = "vnc"
            if s.getConfig()['HYPERVISOR']['ACTIVE'] == "VBOX":
                protocol = "rdp"
            connCreatePayload = {"name":connName,
            "parentIdentifier":"ROOT",
            "protocol":protocol,
            "attributes":{"max-connections":maxConnections, "max-connections-per-user":maxConnectionsPerUser},
            "activeConnections":0,
            "parameters":{
                "port":port,
                "enable-menu-animations":"true",
                "enable-desktop-composition":"true",
                "hostname":ip,
                "color-depth":bitdepth,
                "enable-font-smoothing":"true",
                "ignore-cert":"true",
                "enable-drive":"false",
                "enable-full-window-drag":"true",
                "security":"",
                "password":"",
                "enable-wallpaper":"true",
                "create-drive-path":"true",
                "enable-theming":"true",
                "username":"",
                "console":"",
                "disable-audio":"true",
                "domain":"",
                "drive-path":"",
                "disable-auth":"",
                "server-layout":"",
                "width":width,
                "height":height,
                "dpi":"",
                "resize-method":"display-update",
                "console-audio":"",
                "enable-printing":"",
                "preconnection-id":"",
                "enable-sftp":"",
                "sftp-port":""}}
            res = guacConn.add_connection(connCreatePayload)
            logging.debug("createConnAssociation(): Finished adding connection: " + str(res))
            connID = res['identifier']
            ########Connection Permission for User#########
            connPermPayload = [{"op":"add","path":"/connectionPermissions/"+connID,"value":"READ"}]
            guacConn.grant_permission(username, connPermPayload)
        except Exception as e:
            logging.error("Error in createConnAssociation(). Did not add connection or assign relation!")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            trace_back = traceback.extract_tb(exc_traceback)
            #TODO: This doesn't quite work, but it'd be nice to get the specific error to return it
            for trace in trace_back:
                if "already exists" in str(trace):
                    return "already_exists"
            #traceback.print_exception(exc_type, exc_value, exc_traceback)
            return None

    def removeConnAssociation(self, guacConn, connName):
        logging.debug("removeConnAssociation(): Instantiated")
        try:
            ########Connection removal##########
            logging.debug("removeConnAssociation(): getting connection by name: " + str(connName))
            res = guacConn.get_connection_by_name(connName)
            logging.debug("removeConnAssociation(): result: " + str(res))
            connID = res['identifier']
            ########Connection Permission for User#########
            guacConn.delete_connection(connID)
        except Exception as e:
            logging.error("Error in removeConnAssociation(). Did not remove connection or relation!")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            trace_back = traceback.extract_tb(exc_traceback)
            #traceback.print_exception(exc_type, exc_value, exc_traceback)
            return None

    #abstractmethod
    def getConnectionManageStatus(self):
        logging.debug("getConnectionManageStatus(): instantiated")
        #format: {"readStatus" : self.readStatus, "writeStatus" : self.writeStatus, "usersConnsStatus" : [(username, connName): {"user_status": user_perm, "connStatus": active}] }
        return {"readStatus" : self.readStatus, "writeStatus" : self.writeStatus, "usersConnsStatus" : self.usersConnsStatus}
    
    def getConnectionManageRefresh(self, guacHostname, username, password):
        logging.debug("getConnectionManageStatus(): instantiated")
        self.writeStatus = ConnectionManage.CONNECTION_MANAGE_REFRESHING
        try:
            url_path = "/"
            if guacHostname.startswith("http://"):
                guacConnMethod = 'http'
            elif guacHostname.startswith("https://"):
                guacConnMethod = 'https'
            else:
                #if guacHostname doesn't start with http(s), then we need to add it
                guacHostname = "https://" + guacHostname
                guacConnMethod = 'https'

            if len(guacHostname.split("://")) > 1:
                tmp_path = guacHostname.split("://")[1]
                url_path = "".join(tmp_path.split("/")[1:])
                if url_path.startswith("/") == False:
                    url_path = "/" + url_path
                if url_path.endswith("/") == False:
                    url_path = url_path + "/"

            guacHostname = guacHostname.split("://")[1].split('/')[0]
            self.lock.acquire()
            self.usersConnsStatus.clear()
            guacConn = Guacamole(guacHostname,username=username,password=password,url_path=url_path, method=guacConnMethod)
            #username, connName/VMName, userStatus (admin/etc.), connStatus (connected/not)
            users = guacConn.get_users()
            
            connIDsNames = {}
            activeConns = {}
            allConnections = guacConn.get_connections()
            if 'childConnections' in allConnections:
                for conn in guacConn.get_connections()['childConnections']:
                    connIDsNames[conn['identifier']] = conn['name']
            guac_activeConns = guacConn.get_active_connections()
            for conn in guac_activeConns:
                activeConns[(guac_activeConns[conn]["username"], guac_activeConns[conn]["connectionIdentifier"])] = True

            for user in users:
                #user status first
                perm = guacConn.get_permissions(user)
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
            logging.error("Error in getConnectionManageStatus().")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            trace_back = traceback.extract_tb(exc_traceback)
            traceback.print_exception(exc_type, exc_value, exc_traceback)
            return None
        finally:
            self.lock.release()
            self.writeStatus = ConnectionManage.CONNECTION_MANAGE_COMPLETE

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
