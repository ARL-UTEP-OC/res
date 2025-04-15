import logging
import time
import sys, traceback
import threading
import json
import os
from engine.Manager.ExperimentManage.ExperimentManage import ExperimentManage
from engine.Manager.VMManage.VMManage import VMManage
from engine.Manager.VMManage.ProxmoxManage import ProxmoxManage
from engine.Configuration.ExperimentConfigIO import ExperimentConfigIO
from engine.Configuration.SystemConfigIO import SystemConfigIO

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
            # status = self.vmManage.getManagerStatus()["writeStatus"]
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

                            self.vmManage.cloneVMConfigAll(vmName, cloneVMName, cloneSnapshots, linkedClones, cloneGroupName, internalnets, vrdpPort, username=username, password=password)
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
            self.vmManage.refreshNetwork(username=username, password=password)
            logging.debug("runCreateExperiment(): Complete...")
            print("runCreateExperiment(): Complete...")
        except Exception:
            logging.error("runCloneVM(): Error in runCreateExperiment(): An error occured ")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
        finally:
            self.writeStatus-=1

    def refreshExperimentVMInfo(self, configName, username=None, password=None):
        logging.debug("refreshExperimentVMInfo: refreshAllVMInfo(): instantiated")      
        self.writeStatus+=1
        t = threading.Thread(target=self.runRefreshExperimentVMInfo, args=(configName,username, password))
        t.start()
        t.join()
        self.vmstatus = self.vmManage.getManagerStatus()["vmstatus"]

    def runRefreshExperimentVMInfo(self, configname, username=None, password=None):
        logging.debug("refreshExperimentVMInfo(): instantiated")
        try:
            rolledoutjson = self.eco.getExperimentVMRolledOut(configname)
            clonevmjson, numclones = rolledoutjson
            validvmnames = self.eco.getValidVMsFromTypeName(configname, "", "", rolledoutjson)

            for vm in clonevmjson.keys():
                vmName = vm
                logging.debug("refreshExperimentVMInfo(): working with vm: " + str(vmName))
                #get names for clones
                for cloneinfo in clonevmjson[vm]:
                        cloneVMName = cloneinfo["name"]
                        if cloneVMName not in validvmnames:
                            continue
                        logging.debug("refreshExperimentVMInfo(): Refreshing: " + str(cloneVMName))
                        self.vmManage.refreshVMInfo(cloneVMName, username=username, password=password)
            while self.vmManage.getManagerStatus()["writeStatus"] != VMManage.MANAGER_IDLE:
                #waiting for vmmanager refresh vm to finish reading/writing...
                time.sleep(.1)
            logging.debug("refreshExperimentVMInfo(): Complete...")
        except Exception:
            logging.error("refreshExperimentVMInfo(): Error in refreshExperimentVMInfo(): An error occured ")
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
                            self.vmManage.startVM(cloneVMName, username=username, password=password)
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
                                self.vmManage.guestCommands(cloneVMName, orderedStartupCmds, startupDelay, username=username, password=password)
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
                                self.vmManage.guestCommands(cloneVMName, orderedStartupCmds, startupDelay, username=username, password=password)
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
                                self.vmManage.guestCommands(cloneVMName, orderedStoredCmds, storedDelay, username=username, password=password)
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
                            self.vmManage.suspendVM(cloneVMName, username=username, password=password)
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
                            self.vmManage.pauseVM(cloneVMName, username=username, password=password)
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
                            self.vmManage.snapshotVM(cloneVMName, username=username, password=password)
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
                    self.vmManage.stopVM(cloneVMName, username=username, password=password)
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
                    self.vmManage.removeVM(cloneVMName, username=username, password=password)
                    if removeAdaptors:
                        self.vmManage.removeNetworks(networks)
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
            self.vmManage.refreshNetwork()
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
                    self.vmManage.restoreLatestSnapVM(cloneVMName, username=username, password=password)
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
