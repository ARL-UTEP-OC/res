import logging
import time
import sys, traceback
import threading
import json
from engine.Manager.ExperimentManage.ExperimentManage import ExperimentManage
from engine.Manager.VMManage.VMManage import VMManage
from engine.Manager.VMManage.ProxmoxManage import ProxmoxManage
from engine.Configuration.ExperimentConfigIO import ExperimentConfigIO
from engine.Configuration.SystemConfigIO import SystemConfigIO
from proxmoxer import ProxmoxAPI
from proxmoxer.core import ResourceException
from proxmoxer.backends import ssh_paramiko


class ExperimentManageProxmox(ExperimentManage):
    def __init__(self, vmManage):
        logging.debug("ExperimentManageProxmox(): instantiated")
        ExperimentManage.__init__(self)
        #Create an instance of vmManage
        self.vmManage = vmManage
        self.eco = ExperimentConfigIO.getInstance()
        self.cf = SystemConfigIO()
        self.max_createjobs = self.cf.getConfig()['PROXMOX']['VMANAGE_MAXCREATEJOBS']
        self.snap_waittime = self.cf.getConfig()['PROXMOX']['VMANAGE_SNAPWAITTIME']
        self.vmstatus = {}

        self.proxapi = None
        self.nodename = None
        self.proxssh = None
        self.sshusername = None
        self.sshpassword = None
        self.initialized = False
            
    def isInitialized(self):
        logging.debug("ProxmoxManage: isInitialized(): instantiated")
        return self.initialized

    def setRemoteCreds(self, configname, refresh=False, username=None, password=None):
        logging.info("ProxmoxManage.setRemoteCreds(): Initializing ProxmoxManage; collecting VM information...")
        if username != None and password != None and username.strip() != "" and password.strip() != "" and len(username) > 4:
            self.proxapi, self.nodename = self.getProxAPI(configname, username, password)
            self.proxssh = self.getProxSSH(configname, username=username, password=password)
            if refresh:
                self.vmManage.refreshAllVMInfo(self.proxapi, self.nodename)
                result = self.vmManage.getManagerStatus()["writeStatus"]
                while result != self.vmManage.MANAGER_IDLE:
                #waiting for manager to finish query...
                    result = self.vmManage.getManagerStatus()["writeStatus"]
                    time.sleep(.1)
                self.initialized = True
        logging.info("ProxmoxManage.setRemoteCreds(): Done...")

    def getProxAPI(self, configname, username=None, password=None):
        logging.debug("ProxmoxManage: getProxAPI(): instantiated")
        try:
            vmHostname, vmserversshport, rdiplayhostname, chatserver, challengesserver, keycloakserver, users_file = self.eco.getExperimentServerInfo(configname)
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
            logging.error("Error in getProxAPI(): An error occured when trying to connect to proxmox; possibly incorrect credentials.")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
            self.proxapi = None
            return None

    def getProxSSH(self, configname, username=None, password=None):
        logging.debug("ProxmoxManage: getProxSSH(): instantiated")
        try:
            
            vmHostname, vmserversshport, rdisplayhostname, chatserver, challengesserver, keycloakserver, users_file = self.eco.getExperimentServerInfo(configname)
            server = vmHostname
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
            logging.error("Error in getProxSSH(): An error occured when trying to connect to proxmox with ssh; possibly incorrect credentials.")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
            self.proxssh = None
            return None

    #abstractmethod
    def createExperiment(self, configname, itype="", name="", username=None, password=None):
        logging.debug("createExperiment(): instantiated")
        self.writeStatus+=1
        t = threading.Thread(target=self.runCreateExperiment, args=(configname, itype, name, username, password))
        t.start()
        t.join()
        return 0

    def runCreateExperiment(self, configname, itype, name, username=None, password=None):
        logging.debug("runCreateExperiment(): instantiated")
        try:
            rolledoutjson = self.eco.getExperimentVMRolledOut(configname)
            clonevmjson, numclones = rolledoutjson
            validvmnames = self.eco.getValidVMsFromTypeName(configname, itype, name, rolledoutjson)
            proxapi, nodename = self.getProxAPI(configname, username, password)
            proxssh = self.getProxSSH(configname, username, password)
            for i in range(1, numclones + 1):
                for vm in clonevmjson.keys():
                    vmName = vm
                    logging.debug("runCreateExperiment(): working with vm: " + str(vmName))
                    #Create clones preserving internal networks, etc.
                    if self.vmManage.getVMStatus(vmName) == None:
                        logging.error("VM Name: " + str(vmName) + " does not exist; skipping...")
                        continue
                    refreshedVMName = False
                    #get names for clones
                    for cloneinfo in clonevmjson[vm]:
                        if cloneinfo["groupNum"] == str(i):
                            cloneVMName = cloneinfo["name"]
                            if cloneVMName not in validvmnames:
                                status = self.vmManage.getManagerStatus()["writeStatus"]
                                continue
                            cloneGroupName = cloneinfo["group-name"]
                            cloneSnapshots = cloneinfo["clone-snapshots"]
                            linkedClones = cloneinfo["linked-clones"]
                            internalnets = cloneinfo["networks"]

                            logging.debug("vmName: " + str(vmName) + " cloneVMName: " + str(cloneVMName) + " cloneSnaps: " + str(cloneSnapshots) + " linked: " + str(linkedClones) + " cloneGroupName: " + str(cloneGroupName))

                            # vrdp info
                            vrdpPort = None
                            if "vrdpPort" in cloneinfo:
                                #set interface to vrde
                                logging.debug("runCreateExperiment(): setting up vrdp for " + cloneVMName)
                                vrdpPort = str(cloneinfo["vrdpPort"])

                            self.vmManage.cloneVMConfigAll(vmName, cloneVMName, cloneSnapshots, linkedClones, cloneGroupName, internalnets, vrdpPort, False, proxapi, nodename, proxssh, username, password)
                            logging.info("vmname: " + vmName + " cloneVMName: " + cloneVMName )
                            status = self.vmManage.getManagerStatus()["writeStatus"]
                            while status > int(self.max_createjobs):
                                #waiting for vmmanager clone vm to finish reading/writing...
                                logging.debug("runCreateExperiment(): waiting for vmmanager clone vm to finish reading/writing (cloning set inner)..." + str(status) + ":: " + str(i))
                                print("waiting until it's less than " + self.max_createjobs + " current: " + str(status))
                                time.sleep(1)
                                status = self.vmManage.getManagerStatus()["writeStatus"]

            status = self.vmManage.getManagerStatus()["writeStatus"]
            while status != VMManage.MANAGER_IDLE:
                #waiting for vmmanager clone vm to finish reading/writing...
                logging.debug("runCreateExperiment(): waiting for vmmanager clone vm to finish reading/writing (cloning set outer)..." + str(status) + ":: " + str(i))
                time.sleep(1)
                status = self.vmManage.getManagerStatus()["writeStatus"]
            logging.debug("runCreateExperiment(): finished setting up " + str(numclones) + " clones")
            logging.debug("runCreateExperiment(): applying network configuration")
            print("runCreateExperiment(): applying network configuration")
            self.vmManage.refreshNetwork(proxapi, nodename)
            logging.debug("runCreateExperiment(): Complete...")
            print("runCreateExperiment(): Complete...")
        except Exception:
            logging.error("runCloneVM(): Error in runCreateExperiment(): An error occured ")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
        finally:
            self.writeStatus-=1

    def refreshExperimentVMInfo(self, configName, username=None, password=None):
        logging.debug("refreshExperimentVMInfo: refreshExperimentVMInfo(): instantiated")      
        self.writeStatus+=1
        t = threading.Thread(target=self.runRefreshExperimentVMInfo, args=(configName,username, password))
        t.start()
        t.join()
        self.vmstatus = self.vmManage.getManagerStatus()["vmstatus"]

    def runRefreshExperimentVMInfo(self, configname, username=None, password=None):
        logging.debug("runRefreshExperimentVMInfo(): instantiated")
        try:
            # rolledoutjson = self.eco.getExperimentVMRolledOut(configname)
            # clonevmjson, numclones = rolledoutjson
            # validvmnames = self.eco.getValidVMsFromTypeName(configname, "", "", rolledoutjson)
            proxapi, nodename = self.getProxAPI(configname, username, password)
            self.vmManage.refreshAllVMInfo(proxapi, nodename)

            # for vm in clonevmjson.keys():
            #     logging.debug("runRefreshExperimentVMInfo(): working with vm: " + str(vm))
            #     self.vmManage.refreshVMInfo(vm, None, proxapi, nodename)
            #     #get names for clones
            #     for cloneinfo in clonevmjson[vm]:
            #             cloneVMName = cloneinfo["name"]
            #             if cloneVMName not in validvmnames:
            #                 continue
            #             logging.debug("runRefreshExperimentVMInfo(): Refreshing: " + str(cloneVMName))
            #             self.vmManage.refreshVMInfo(cloneVMName, None, proxapi, nodename)
            while self.vmManage.getManagerStatus()["writeStatus"] != VMManage.MANAGER_IDLE:
                #waiting for vmmanager refresh vm to finish reading/writing...
                time.sleep(.1)
            logging.debug("runRefreshExperimentVMInfo(): Complete...")
        except Exception:
            logging.error("runRefreshExperimentVMInfo(): Error in runRefreshExperimentVMInfo(): An error occured ")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
        finally:
            self.writeStatus-=1

    #abstractmethod
    def startExperiment(self, configname, itype="", name="", username=None, password=None):
        logging.debug("startExperiment(): instantiated")
        self.writeStatus+=1
        t = threading.Thread(target=self.runStartExperiment, args=(configname,itype, name, username, password))
        t.start()
        t.join()
        return 0

    def runStartExperiment(self, configname, itype, name, username=None, password=None):
        logging.debug("runStartExperiment(): instantiated")
        try:
            #Will first clone the vms and then run their start commands if any
            #call vmManage to start clones as specified in config file; wait and query the vmManage status, and then set the complete status
            rolledoutjson = self.eco.getExperimentVMRolledOut(configname)
            clonevmjson, numclones = rolledoutjson
            validvmnames = self.eco.getValidVMsFromTypeName(configname, itype, name, rolledoutjson)
            proxapi, nodename = self.getProxAPI(configname, username, password)
            for i in range(1, numclones + 1):
                for vm in clonevmjson.keys(): 
                    vmName = vm
                    logging.debug("runStartExperiment(): working with vm: " + str(vmName))
                    #get names for clones and start them
                    for cloneinfo in clonevmjson[vm]:
                        if cloneinfo["groupNum"] == str(i):
                            cloneVMName = cloneinfo["name"]
                            if cloneVMName not in validvmnames:
                                continue
                            #Check if clone exists and then run it if it does
                            if self.vmManage.getVMStatus(vmName) == None:
                                logging.error("runStartExperiment(): VM Name: " + str(vmName) + " does not exist; skipping...")
                                continue
                            logging.debug("runStartExperiment(): Starting: " + str(vmName))
                            self.vmManage.startVM(cloneVMName, proxapi, nodename)
            while self.vmManage.getManagerStatus()["writeStatus"] != VMManage.MANAGER_IDLE:
            #waiting for vmmanager start vm to finish reading/writing...
                time.sleep(.1)
            #now that the VMs have started, we want to run the commands on each; no waiting needed
            for i in range(1, numclones + 1):
                for vm in clonevmjson.keys():
                    vmName = vm
                    logging.debug("runStartExperiment(): working with vm: " + str(vmName))
                    #get names for clones and start them
                    for cloneinfo in clonevmjson[vm]:
                        if cloneinfo["groupNum"] == str(i):
                            cloneVMName = cloneinfo["name"]
                            if cloneVMName not in validvmnames:
                                continue
                            #Check if clone exists and then run it if it does
                            if self.vmManage.getVMStatus(cloneVMName) == None:
                                logging.error("runStartExperiment(): VM Name: " + str(cloneVMName) + " does not exist; skipping...")
                                continue
                            logging.debug("runStartExperiment(): command(s) setup on " + str(cloneVMName) )
                            #put all of the commands into a single list, based on sequence numbers:
                            if cloneinfo["startup-cmds"] != None:
                                startupCmds = cloneinfo["startup-cmds"]
                                startupDelay = cloneinfo["startup-cmds-delay"]
                                #format them into a list; based on execution order
                                orderedStartupCmds = []
                                for sequence in sorted(startupCmds):
                                    cmds = startupCmds[sequence]
                                    for mcmd in cmds:
                                        #from the tuple, just get the "exec" or command, not hypervisor
                                        #substitute out any template variables
                                        mcmd = (mcmd[0],mcmd[1].replace("{{RES_CloneName}}","\""+str(cloneVMName)+"\""))
                                        mcmd = (mcmd[0],mcmd[1].replace("{{RES_CloneNumber}}",str(i)))
                                        orderedStartupCmds.append(mcmd[1])
                                logging.debug("runStartExperiment(): sending command(s) for " + str(cloneVMName) + str(orderedStartupCmds))
                                self.vmManage.guestCommands(cloneVMName, orderedStartupCmds, startupDelay, proxapi, nodename)
            logging.debug("runStartExperiment(): Complete...")
        except Exception:
            logging.error("runStartExperiment(): Error in runStartExperiment(): An error occured ")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
        finally:
            self.writeStatus-=1

    def guestCmdsExperiment(self, configname, itype="", name="", username=None, password=None):
        logging.debug("guestCmdsExperiment(): instantiated")
        self.writeStatus+=1
        t = threading.Thread(target=self.runGuestCmdsExperiment, args=(configname, itype, name, username, password))
        t.start()
        t.join()
        return 0

    def runGuestCmdsExperiment(self, configname, itype, name, username=None, password=None):
        logging.debug("runGuestCmdsExperiment(): instantiated")
        try:
            rolledoutjson = self.eco.getExperimentVMRolledOut(configname)
            clonevmjson, numclones = rolledoutjson
            validvmnames = self.eco.getValidVMsFromTypeName(configname, itype, name, rolledoutjson)
            proxapi, nodename = self.getProxAPI(configname, username, password)
            for i in range(1, numclones + 1):
                for vm in clonevmjson.keys():
                    vmName = vm
                    logging.debug("runGuestCmdsExperiment(): working with vm: " + str(vmName))
                    #get names for clones and start them
                    for cloneinfo in clonevmjson[vm]:
                        if cloneinfo["groupNum"] == str(i):
                            cloneVMName = cloneinfo["name"]
                            if cloneVMName not in validvmnames:
                                continue
                            #Check if clone exists and then run it if it does
                            if self.vmManage.getVMStatus(cloneVMName) == None:
                                logging.error("runGuestCmdsExperiment(): VM Name: " + str(cloneVMName) + " does not exist; skipping...")
                                continue
                            logging.debug("runGuestCmdsExperiment(): command(s) setup on " + str(cloneVMName) )
                            #put all of the commands into a single list, based on sequence numbers:
                            if cloneinfo["startup-cmds"] != None:
                                startupCmds = cloneinfo["startup-cmds"]
                                startupDelay = cloneinfo["startup-cmds-delay"]
                                #format them into a list; based on execution order
                                orderedStartupCmds = []
                                for sequence in sorted(startupCmds):
                                    cmds = startupCmds[sequence]
                                    for mcmd in cmds:
                                        #from the tuple, just get the "exec" or command, not hypervisor
                                        #substitute out any template variables
                                        mcmd = (mcmd[0],mcmd[1].replace("{{RES_CloneName}}","\""+str(cloneVMName)+"\""))
                                        mcmd = (mcmd[0],mcmd[1].replace("{{RES_CloneNumber}}",str(i)))
                                        orderedStartupCmds.append(mcmd[1])
                                logging.debug("runGuestCmdsExperiment(): sending command(s) for " + str(cloneVMName) + str(orderedStartupCmds))
                                self.vmManage.guestCommands(cloneVMName, orderedStartupCmds, startupDelay, proxapi, nodename)
            while self.vmManage.getManagerStatus()["writeStatus"] != VMManage.MANAGER_IDLE:
                #waiting for vmmanager start vm to finish reading/writing...
                time.sleep(.1)
            logging.debug("runGuestCmdsExperiment(): Complete...")
        except Exception:
            logging.error("runGuestCmdsExperiment(): Error in runGuestCmdsExperiment(): An error occured ")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
        finally:
            self.writeStatus-=1

    def guestStoredCmdsExperiment(self, configname, itype="", name="", username=None, password=None):
        logging.debug("runGuestStoredCmdsExperiment(): instantiated")
        self.writeStatus+=1
        t = threading.Thread(target=self.runGuestStoredCmdsExperiment, args=(configname, itype, name, username, password))
        t.start()
        t.join()
        return 0

    def runGuestStoredCmdsExperiment(self, configname, itype, name, username=None, password=None):
        logging.debug("runGuestStoredCmdsExperiment(): instantiated")
        try:
            rolledoutjson = self.eco.getExperimentVMRolledOut(configname)
            clonevmjson, numclones = rolledoutjson
            validvmnames = self.eco.getValidVMsFromTypeName(configname, itype, name, rolledoutjson)
            proxapi, nodename = self.getProxAPI(configname, username, password)
            for i in range(1, numclones + 1):
                for vm in clonevmjson.keys():
                    vmName = vm
                    logging.debug("runGuestStoredCmdsExperiment(): working with vm: " + str(vmName))
                    #get names for clones and start them
                    for cloneinfo in clonevmjson[vm]:
                        if cloneinfo["groupNum"] == str(i):
                            cloneVMName = cloneinfo["name"]
                            if cloneVMName not in validvmnames:
                                continue
                            #Check if clone exists and then run it if it does
                            if self.vmManage.getVMStatus(cloneVMName) == None:
                                logging.error("runGuestStoredCmdsExperiment(): VM Name: " + str(cloneVMName) + " does not exist; skipping...")
                                continue
                            logging.debug("runGuestStoredCmdsExperiment(): command(s) setup on " + str(cloneVMName) )
                            #put all of the commands into a single list, based on sequence numbers:
                            if cloneinfo["stored-cmds"] != None:
                                storedCmds = cloneinfo["stored-cmds"]
                                storedDelay = cloneinfo["stored-cmds-delay"]
                                #format them into a list; based on execution order
                                orderedStoredCmds = []
                                for sequence in sorted(storedCmds):
                                    cmds = storedCmds[sequence]
                                    for mcmd in cmds:
                                        #from the tuple, just get the "exec" or command, not hypervisor
                                        #substitute out any template variables
                                        mcmd = (mcmd[0],mcmd[1].replace("{{RES_CloneName}}","\""+str(cloneVMName)+"\""))
                                        mcmd = (mcmd[0],mcmd[1].replace("{{RES_CloneNumber}}",str(i)))
                                        orderedStoredCmds.append(mcmd[1])
                                logging.debug("runGuestStoredCmdsExperiment(): sending command(s) for " + str(cloneVMName) + str(orderedStoredCmds))
                                self.vmManage.guestCommands(cloneVMName, orderedStoredCmds, storedDelay, proxapi, nodename)
            while self.vmManage.getManagerStatus()["writeStatus"] != VMManage.MANAGER_IDLE:
                #waiting for vmmanager to finish reading/writing...
                time.sleep(.1)
            logging.debug("runGuestStoredCmdsExperiment(): Complete...")
        except Exception:
            logging.error("runGuestStoredCmdsExperiment(): Error in runGuestStoredCmdsExperiment(): An error occured ")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
        finally:
            self.writeStatus-=1

    #abstractmethod
    def suspendExperiment(self, configname, itype="", name="", username=None, password=None):
        logging.debug("suspendExperiment(): instantiated")
        self.writeStatus+=1
        t = threading.Thread(target=self.runSuspendExperiment, args=(configname, itype, name, username, password))
        t.start()
        t.join()
        return 0

    def runSuspendExperiment(self, configname, itype, name, username=None, password=None):
        logging.debug("runSuspendExperiment(): instantiated")
        try:
            #call vmManage to suspend clones as specified in config file; wait and query the vmManage status, and then set the complete status
            rolledoutjson = self.eco.getExperimentVMRolledOut(configname)
            clonevmjson, numclones = rolledoutjson
            validvmnames = self.eco.getValidVMsFromTypeName(configname, itype, name, rolledoutjson)
            proxapi, nodename = self.getProxAPI(configname, username, password)
            for i in range(1, numclones + 1):
                for vm in clonevmjson.keys(): 
                    vmName = vm
                    logging.debug("runSuspendExperiment(): working with vm: " + str(vmName))
                    #get names for clones and suspend them
                    for cloneinfo in clonevmjson[vm]:
                        if cloneinfo["groupNum"] == str(i):
                            cloneVMName = cloneinfo["name"]
                            if cloneVMName not in validvmnames:
                                continue
                            #Check if clone exists and then run it if it does
                            if self.vmManage.getVMStatus(vmName) == None:
                                logging.error("runSuspendExperiment(): VM Name: " + str(vmName) + " does not exist; skipping...")
                                continue
                            logging.debug("runSuspendExperiment(): Suspending: " + str(vmName))
                            self.vmManage.suspendVM(cloneVMName, proxapi, nodename)
            while self.vmManage.getManagerStatus()["writeStatus"] != VMManage.MANAGER_IDLE:
                #waiting for vmmanager suspend vm to finish reading/writing...
                time.sleep(.1)
            logging.debug("runSuspendingExperiment(): Complete...")
        except Exception:
            logging.error("runSuspendingExperiment(): Error in runSuspendingExperiment(): An error occured ")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
        finally:
            self.writeStatus-=1

    #abstractmethod
    def pauseExperiment(self, configname, itype="", name="", username=None, password=None):
        logging.debug("pauseExperiment(): instantiated")
        self.writeStatus+=1
        t = threading.Thread(target=self.runPauseExperiment, args=(configname, itype, name, username, password))
        t.start()
        t.join()
        return 0

    def runPauseExperiment(self, configname, itype, name, username=None, password=None):
        logging.debug("runPauseExperiment(): instantiated")
        try:
            #call vmManage to pause clones as specified in config file; wait and query the vmManage status, and then set the complete status
            rolledoutjson = self.eco.getExperimentVMRolledOut(configname)
            clonevmjson, numclones = rolledoutjson
            validvmnames = self.eco.getValidVMsFromTypeName(configname, itype, name, rolledoutjson)
            proxapi, nodename = self.getProxAPI(configname, username, password)
            for i in range(1, numclones + 1):
                for vm in clonevmjson.keys(): 
                    vmName = vm
                    logging.debug("runPauseExperiment(): working with vm: " + str(vmName))
                    #get names for clones and pausing them
                    for cloneinfo in clonevmjson[vm]:
                        if cloneinfo["groupNum"] == str(i):
                            cloneVMName = cloneinfo["name"]
                            if cloneVMName not in validvmnames:
                                continue                            
                            #Check if clone exists and then run it if it does
                            if self.vmManage.getVMStatus(vmName) == None:
                                logging.error("runPauseExperiment(): VM Name: " + str(vmName) + " does not exist; skipping...")
                                continue
                            logging.debug("runPauseExperiment(): Pausing: " + str(vmName))
                            self.vmManage.pauseVM(cloneVMName, proxapi, nodename)
            while self.vmManage.getManagerStatus()["writeStatus"] != VMManage.MANAGER_IDLE:
                #waiting for vmmanager pause vm to finish reading/writing...
                time.sleep(.1)
            logging.debug("runPauseExperiment(): Complete...")
        except Exception:
            logging.error("runPauseExperiment(): Error in runPauseExperiment(): An error occured ")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
        finally:
            self.writeStatus-=1

    #abstractmethod
    def snapshotExperiment(self, configname, itype="", name="", username=None, password=None):
        logging.debug("snapshotExperiment(): instantiated")
        self.writeStatus+=1
        t = threading.Thread(target=self.runSnapshotExperiment, args=(configname, itype, name, username, password))
        t.start()
        t.join()
        return 0

    def runSnapshotExperiment(self, configname, itype, name, username=None, password=None):
        logging.debug("runSnapshotExperiment(): instantiated")
        try:
            #call vmManage to snapshot clones as specified in config file; wait and query the vmManage status, and then set the complete status
            rolledoutjson = self.eco.getExperimentVMRolledOut(configname)
            clonevmjson, numclones = rolledoutjson
            validvmnames = self.eco.getValidVMsFromTypeName(configname, itype, name, rolledoutjson)
            proxapi, nodename = self.getProxAPI(configname, username, password)
            for i in range(1, numclones + 1):
                for vm in clonevmjson.keys(): 
                    vmName = vm
                    logging.debug("runSnapshotExperiment(): working with vm: " + str(vmName))
                    #get names for clones and pausing them
                    for cloneinfo in clonevmjson[vm]:
                        if cloneinfo["groupNum"] == str(i):
                            cloneVMName = cloneinfo["name"]
                            if cloneVMName not in validvmnames:
                                continue
                            #Check if clone exists and then run it if it does
                            if self.vmManage.getVMStatus(vmName) == None:
                                logging.error("runSnapshotExperiment(): VM Name: " + str(vmName) + " does not exist; skipping...")
                                continue
                            logging.debug("runSnapshotExperiment(): Snapshotting: " + str(vmName))
                            self.vmManage.snapshotVM(cloneVMName, proxapi, nodename)
                            status = self.vmManage.getManagerStatus()["writeStatus"]
                            #if snaps are taken too fast, the lock on /etc/pve/ will cause an error... need a wait time in-between
                            time.sleep(float(self.snap_waittime))
            while self.vmManage.getManagerStatus()["writeStatus"] != VMManage.MANAGER_IDLE:
                #waiting for vmmanager snapshot vm to finish reading/writing...
                time.sleep(.1)
            logging.debug("runSnapshotExperiment(): Complete...")
        except Exception:
            logging.error("runSnapshotExperiment(): Error in runSnapshotExperiment(): An error occured ")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
        finally:
            self.writeStatus-=1

    #abstractmethod
    def stopExperiment(self, configname, itype="", name="", username=None, password=None):
        logging.debug("stopExperiment(): instantiated")
        self.writeStatus+=1
        t = threading.Thread(target=self.runStopExperiment, args=(configname, itype, name, username, password))
        t.start()
        t.join()
        return 0

    def runStopExperiment(self, configname, itype, name, username=None, password=None):
        logging.debug("runStopExperiment(): instantiated")
        try:
            #call vmManage to stop clones as specified in config file; wait and query the vmManage status, and then set the complete status
            rolledoutjson = self.eco.getExperimentVMRolledOut(configname)
            clonevmjson, numclones = rolledoutjson
            validvmnames = self.eco.getValidVMsFromTypeName(configname, itype, name, rolledoutjson)
            proxapi, nodename = self.getProxAPI(configname, username, password)
            for vm in clonevmjson.keys(): 
                vmName = vm
                logging.debug("runStopExperiment(): working with vm: " + str(vmName))
                #get names for clones and stop them
                for cloneinfo in clonevmjson[vm]:
                    cloneVMName = cloneinfo["name"]
                    if cloneVMName not in validvmnames:
                        continue
                    #Check if clone exists and then run it if it does
                    if self.vmManage.getVMStatus(vmName) == None:
                        logging.error("runStopExperiment(): VM Name: " + str(vmName) + " does not exist; skipping...")
                        continue
                    logging.debug("runStopExperiment(): Stopping: " + str(vmName))
                    self.vmManage.stopVM(cloneVMName, proxapi, nodename)
            while self.vmManage.getManagerStatus()["writeStatus"] != VMManage.MANAGER_IDLE:
                #waiting for vmmanager stop vm to finish reading/writing...
                time.sleep(.1)
            logging.debug("runStopExperiment(): Complete...")
        except Exception:
            logging.error("runStopExperiment(): Error in runStopExperiment(): An error occured ")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
        finally:
            self.writeStatus-=1

    #abstractmethod
    def removeExperiment(self, configname, itype="", name="", username=None, password=None):
        logging.debug("removeExperiment(): instantiated")
        self.writeStatus+=1
        t = threading.Thread(target=self.runRemoveExperiment, args=(configname, itype, name, username, password))
        t.start()
        t.join()
        return 0
        
    def runRemoveExperiment(self, configname, itype, name, username=None, password=None):
        logging.debug("runRemoveExperiment(): instantiated")
        try:
            #call vmManage to remove clones as specified in config file; wait and query the vmManage status, and then set the complete status
            rolledoutjson = self.eco.getExperimentVMRolledOut(configname)
            clonevmjson, numclones = rolledoutjson
            validvmnames = self.eco.getValidVMsFromTypeName(configname, itype, name, rolledoutjson)
            proxapi, nodename = self.getProxAPI(configname, username, password)
            #if itype and name are "" (remove all), then also remove the network adaptors
            removeAdaptors = False
            removeUnusedLVM = False
            if itype == "" and name == "":
                removeAdaptors = True
                removeUnusedLVM = True
            for vm in clonevmjson.keys(): 
                vmName = vm
                logging.debug("runRemoveExperiment(): working with vm: " + str(vmName))
                #get names for clones and remove them
                for cloneinfo in clonevmjson[vm]:
                    cloneVMName = cloneinfo["name"]
                    networks = cloneinfo["networks"]
                    if cloneVMName not in validvmnames:
                        continue
                    #Check if clone exists and then remove it if it does
                    if self.vmManage.getVMStatus(vmName) == None:
                        logging.error("runRemoveExperiment(): VM Name: " + str(vmName) + " does not exist; skipping...")
                        continue
                    logging.debug("runRemoveExperiment(): Removing: " + str(cloneVMName))
                    self.vmManage.removeVM(cloneVMName, proxapi, nodename)
                    if removeAdaptors:
                        self.vmManage.removeNetworks(networks, proxapi, nodename)
            while self.vmManage.getManagerStatus()["writeStatus"] != VMManage.MANAGER_IDLE:
                #waiting for vmmanager stop vm to finish reading/writing...
                time.sleep(.1)
            logging.debug("runRemoveExperiment(): Complete...")
            #Remove old lvm that are inactive
            if removeUnusedLVM:
                # self.writeStatus+=1
                # self.vmManage.runRemoteCmds(["lvscan  | grep inactive | awk -F \"'\" '{print $2}' | xargs lvremove"])
                pass
            #now update the network configurations
            self.vmManage.refreshNetwork(proxapi, nodename)
        except Exception:
            logging.error("runRemoveExperiment(): Error in runRemoveExperiment(): An error occured ")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
        finally:
            self.writeStatus-=1

    #abstractmethod
    def restoreExperiment(self, configname, itype="", name="", username=None, password=None):
        logging.debug("restoreExperimentStates(): instantiated")
        self.writeStatus+=1
        t = threading.Thread(target=self.runRestoreExperiment, args=(configname, itype, name, username, password))
        t.start()
        t.join()
        return 0    

    def runRestoreExperiment(self, configname, itype, name, username=None, password=None):
        logging.debug("runRestoreExperiment(): instantiated")
        try:
            #call vmManage to restore clones as specified in config file; wait and query the vmManage status, and then set the complete status
            rolledoutjson = self.eco.getExperimentVMRolledOut(configname)
            clonevmjson, numclones = rolledoutjson
            validvmnames = self.eco.getValidVMsFromTypeName(configname, itype, name, rolledoutjson)
            proxapi, nodename = self.getProxAPI(configname, username, password)
            for vm in clonevmjson.keys(): 
                vmName = vm
                logging.debug("runRestoreExperiment(): working with vm: " + str(vmName))
                #get names for clones and restore them
                for cloneinfo in clonevmjson[vm]:
                    cloneVMName = cloneinfo["name"]
                    if cloneVMName not in validvmnames:
                        continue
                    #Check if clone exists and then run it if it does
                    if self.vmManage.getVMStatus(vmName) == None:
                        logging.error("runRestoreExperiment(): VM Name: " + str(vmName) + " does not exist; skipping...")
                        continue
                    logging.debug("runRestoreExperiment(): Restoring latest for : " + str(cloneVMName))
                    self.vmManage.restoreLatestSnapVM(cloneVMName, proxapi, nodename)
                    while self.vmManage.getManagerStatus()["writeStatus"] != VMManage.MANAGER_IDLE:
                        #waiting for vmmanager stop vm to finish reading/writing...
                        time.sleep(.1)
            logging.debug("runRestoreExperiment(): Complete...")
        except Exception:
            logging.error("runRestoreExperiment(): Error in runRestoreExperiment(): An error occured ")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
        finally:
            self.writeStatus-=1

    def getExperimentManageStatus(self):
        logging.debug("getExperimentManageStatus(): instantiated")
        return {"readStatus" : self.readStatus, "writeStatus" : self.writeStatus, "vmstatus" : self.vmstatus}

    def getExperimentVMNames(self, experimentname):
        logging.debug("getExperimentVMNames(): instantiated")
        jsondata = self.eco.getExperimentXMLFileData(experimentname)
        vms = jsondata["xml"]["testbed-setup"]["vm-set"]
        vmNames = []
        
        if isinstance(vms["vm"], list) == False:
            vms["vm"] = [vms["vm"]]
        for name in vms["vm"]:    
            vmNames.append(name["name"])
        return vmNames

    def getExperimentMaterialNames(self, experimentname):
        logging.debug("getExperimentMaterialNames(): instantiated")
        #TODO: implement this method

if __name__ == "__main__":
    logging.getLogger().setLevel(logging.DEBUG)
    logging.debug("Starting Program")

    logging.debug("Instantiating Engine")
    vbm = ProxmoxManage()
    e = ExperimentManageProxmox(vbm)
    ####---Create Experiment Test#####
    logging.info("Creating Experiment")
    e.createExperiment("sample")
    result = e.getExperimentManageStatus()["writeStatus"]
    while result != e.EXPERIMENT_MANAGE_COMPLETE:
        time.sleep(.1)
        logging.debug("Waiting for experiment create to complete...")
        result = e.getExperimentManageStatus()["writeStatus"]
    
    #####---Start Experiment Test#####
    logging.info("Starting Experiment")
    e.startExperiment("sample")
    while e.getExperimentManageStatus()["writeStatus"] != e.EXPERIMENT_MANAGE_COMPLETE:
        time.sleep(.1)
        logging.debug("Waiting for experiment start to complete...")
    logging.debug("Experiment start complete.")    

    #####---Pause Experiment Test#####
    logging.info("Pause Experiment")
    e.pauseExperiment("sample")
    while e.getExperimentManageStatus()["writeStatus"] != e.EXPERIMENT_MANAGE_COMPLETE:
        time.sleep(.1)
        logging.debug("Waiting for experiment pause to complete...")
    logging.debug("Experiment pause complete.")

    #####---Snapshot Experiment Test#####
    logging.info("Snapshot Experiment")
    e.snapshotExperiment("sample")
    while e.getExperimentManageStatus()["writeStatus"] != e.EXPERIMENT_MANAGE_COMPLETE:
        time.sleep(.1)
        logging.debug("Waiting for experiment snapshot to complete...")
    logging.debug("Experiment snapshot complete.")

    #####---Stop Experiment Test#####
    logging.info("Stopping Experiment")
    e.stopExperiment("sample")
    while e.getExperimentManageStatus()["writeStatus"] != e.EXPERIMENT_MANAGE_COMPLETE:
        time.sleep(.1)
        logging.debug("Waiting for experiment stop to complete...")
    logging.debug("Experiment stop complete.")    

    #####---Suspend Experiment Test#####
    logging.info("Suspend Experiment")
    e.suspendExperiment("sample")
    while e.getExperimentManageStatus()["writeStatus"] != e.EXPERIMENT_MANAGE_COMPLETE:
        time.sleep(.1)
        logging.debug("Waiting for experiment suspend to complete...")
    logging.debug("Experiment suspend complete.")    

    #####---Restore Experiment Test#####
    logging.info("Restoring Experiment")
    e.restoreExperiment("sample")
    while e.getExperimentManageStatus()["writeStatus"] != e.EXPERIMENT_MANAGE_COMPLETE:
        time.sleep(.1)
        logging.debug("Waiting for experiment stop to complete...")
    logging.debug("Experiment stop complete.")

    # #####---Remove Experiment Test#####
    logging.info("Removing Experiment")
    e.removeExperiment("sample")
    result = e.getExperimentManageStatus()["writeStatus"]
    while result != e.EXPERIMENT_MANAGE_COMPLETE:
        time.sleep(.1)
        logging.debug("Waiting for experiment create to complete...")
        result = e.getExperimentManageStatus()["writeStatus"]
