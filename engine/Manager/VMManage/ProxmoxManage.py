from subprocess import Popen, PIPE
import subprocess
from sys import argv, platform
import sys, traceback
import logging
import threading
import sys
import time
import shlex
from engine.Manager.VMManage.VMManage import VMManage
from engine.Manager.VMManage.VM import VM
import re
import os
from engine.Configuration.SystemConfigIO import SystemConfigIO
from threading import RLock
from proxmoxer import ProxmoxAPI
from proxmoxer.core import ResourceException
from proxmoxer.backends import ssh_paramiko

class ProxmoxManage(VMManage):
    def __init__(self, initializeVMManage=False, username=None, password=None):
        logging.debug("ProxmoxManage.__init__(): instantiated")
        VMManage.__init__(self)
        self.cf = SystemConfigIO()
        # A lock for acces/updates to self.vms
        self.lock = RLock()
        self.vms = {}
        self.tempVMs = {}
        if initializeVMManage:
            self.refreshAllVMInfo()
            result = self.getManagerStatus()["writeStatus"]
            while result != self.MANAGER_IDLE:
            #waiting for manager to finish query...
                result = self.getManagerStatus()["writeStatus"]
                time.sleep(.1)

    def basic_blocking_task_status(self, proxmox_api, task_id, node_name):
        data = {"status": ""}
        while (data["status"] != "stopped"):
            data = proxmox_api.nodes(node_name).tasks(task_id).status.get()
        return data

    def configureVMNet(self, vmName, netNum, netName, username=None, password=None):
        logging.debug("ProxmoxManage: configureVMNet(): instantiated")
        #check to make sure the vm is known, if not should refresh or check name:
        exists = False
        try:
            self.lock.acquire()
            exists = vmName in self.vms
            if not exists:
                logging.error("configureVMNet(): " + vmName + " not found in list of known vms: \r\n" + str(vmName))
                return -1
            self.readStatus = VMManage.MANAGER_READING
            self.writeStatus += 1
            t = threading.Thread(target=self.runConfigureVMNet, args=(vmName, netNum, netName, username, password))
            t.start()
            return 0
        finally:
            self.lock.release()

    def configureVMNets(self, vmName, internalNets, username=None, password=None):
        logging.debug("ProxmoxManage: configureVMNets(): instantiated")
        #check to make sure the vm is known, if not should refresh or check name:
        exists = False
        try:
            self.lock.acquire()
            exists = vmName in self.vms
            if not exists:
                logging.error("configureVMNets(): " + vmName + " not found in list of known vms: \r\n" + str(vmName))
                return -1
            self.readStatus = VMManage.MANAGER_READING
            self.writeStatus += 1
            t = threading.Thread(target=self.runConfigureVMNets, args=(vmName, internalNets, username, password))
            t.start()
            return 0
        finally:
            self.lock.release()

    def runConfigureVMNets(self, vmName, internalNets, username=None, password=None):
        try:
            logging.debug("runConfigureVMNets(): instantiated")
            self.readStatus = VMManage.MANAGER_READING
            logging.debug("runConfigureVMNets(): adding 1 "+ str(self.writeStatus))
            cloneNetNum = 1
            logging.debug("runConfigureVMNets(): Processing internal net names: " + str(internalNets))
            vmUUID = ""
            try:
                self.lock.acquire()
                vmUUID = str(self.vms[vmName].UUID)
            finally:
                self.lock.release()
            try:
                server = self.cf.getConfig()['PROXMOX']['VMANAGE_SERVER']
                port = self.cf.getConfig()['PROXMOX']['VMANAGE_APIPORT']
                nodename = self.cf.getConfig()['PROXMOX']['VMANAGE_NODE_NAME']
                proxapi = ProxmoxAPI(server, port=port, user=username, password=password, verify_ssl=False)
            except Exception:
                #logging.error("Error in <>(): An error occured ")
                logging.error("Error in runConfigureVMNets(): An error occured when trying to connect to proxmox")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
                return None

            for internalnet in internalNets:
                try:
                    ifaces = proxapi.nodes(nodename)('network').get(type='bridge')
                except Exception:
                    #logging.error("Error in <>(): An error occured ")
                    logging.error("Error in runConfigureVMNets(): An error occured when trying to get bridges")
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    traceback.print_exception(exc_type, exc_value, exc_traceback)

                try:
                    #create bridge if it doesn't exist
                    res = proxapi.nodes(nodename)('network').post(iface=str(internalnet),node=nodename,type='bridge')
                    self.basic_blocking_task_status(proxapi, res, nodename)
                    res = proxapi.nodes(nodename)('network').put()
                    self.basic_blocking_task_status(proxapi, res, nodename)
                except ResourceException:
                    #logging.error("Error in <>(): An error occured ")
                    logging.error("Error in runConfigureVMNets(): An error occured; interface may already exist: " + str(internalnet))
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    traceback.print_exception(exc_type, exc_value, exc_traceback)
                    continue

                #assign net to bridge
                kwargs = {f'net{cloneNetNum}': 'e1000,bridge='+str(internalnet)}
                try:
                    logging.info("runConfigureVMNets(): Configuring Interface: " + str(vmUUID) + " " + str(**kwargs))
                    res = proxapi.nodes(nodename)('qemu')(vmUUID)('config').post(**kwargs)
                    self.basic_blocking_task_status(proxapi, res, nodename)
                except Exception:
                    logging.error("Error in runConfigureVMNets(): An error occured when trying to configure vm network device")
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    traceback.print_exception(exc_type, exc_value, exc_traceback)
                logging.info("Command Output: "+ str(res))
                cloneNetNum += 1            
           
            logging.debug("runConfigureVMNets(): Thread completed")
        except Exception:
            logging.error("runConfigureVMNets() Error")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
        finally:
            self.readStatus = VMManage.MANAGER_IDLE
            self.writeStatus -= 1
            logging.debug("runConfigureVMNets(): sub 1 "+ str(self.writeStatus))

    def guestCommands(self, vmName, cmds, delay=0, username=None, password=None):
        logging.debug("guestCommands(): instantiated")
        # #check to make sure the vm is known, if not should refresh or check name:
        # exists = False
        # try:
        #     self.lock.acquire()
        #     exists = vmName in self.vms
        #     if not exists:
        #         logging.error("guestCommands(): " + vmName + " not found in list of known vms: \r\n" + str(vmName))
        #         return -1
        #     self.guestThreadStatus += 1
        #     t = threading.Thread(target=self.runGuestCommands, args=(vmName, cmds, delay, username, password))
        #     t.start()
        #     return 0
        # finally:
        #     self.lock.release()

    def runGuestCommands(self, vmName, cmds, delay, username=None, password=None):
        logging.debug("ProxmoxManage: runGuestCommands(): instantiated")
        # try:
        #     logging.debug("runGuestCommands(): adding 1 "+ str(self.writeStatus))
        #     cmd = "N/A"
        #     #if a delay was specified... wait
        #     time.sleep(int(delay))
        #     for cmd in cmds:
        #         vmCmd = self.vmanage_path + " guestcontrol " + str(self.vms[vmName].UUID) + " " + cmd
        #         logging.info("runGuestCommands(): Running " + vmCmd)
        #         p = Popen(vmCmd, stdout=PIPE, stderr=PIPE, encoding="utf-8")
        #         while True:
        #             out = p.stdout.readline()
        #             if out == '' and p.poll() != None:
        #                 break
        #             if out != '':
        #                 logging.info("Command Output: " + out)
        #         p.wait()

        #     logging.debug("runGuestCommands(): Thread completed")
        # except Exception:
        #     logging.error("runGuestCommands() Error: " + " cmd: " + cmd)
        #     exc_type, exc_value, exc_traceback = sys.exc_info()
        #     traceback.print_exception(exc_type, exc_value, exc_traceback)
        # finally:
        #     self.guestThreadStatus -= 1
        #     logging.debug("runGuestCommands(): sub thread 1 "+ str(self.writeStatus))

    def refreshAllVMInfo(self, username=None, password=None):
        logging.debug("ProxmoxManage: refreshAllVMInfo(): instantiated")
        logging.debug("getListVMS() Starting List VMs thread")
        self.readStatus = VMManage.MANAGER_READING
        self.writeStatus += 1
        t = threading.Thread(target=self.runVMSInfo, args=(username, password))
        t.start()
        
    def refreshVMInfo(self, vmName, username=None, password=None):
        logging.debug("ProxmoxManage: refreshVMInfo(): instantiated: " + str(vmName))
        logging.debug("refreshVMInfo() refresh VMs thread")
        #check to make sure the vm is known, if not should refresh or check name:
        exists = False
        try:
            self.lock.acquire()
            exists = vmName in self.vms
            if not exists:
                logging.warning("refreshVMInfo(): " + vmName + " not found in list of known vms... refreshing all\r\n")
                t = threading.Thread(target=self.runVMSInfo, args=(username, password))
                self.readStatus = VMManage.MANAGER_READING
                self.writeStatus += 1
                t.start()
            else:
                self.readStatus = VMManage.MANAGER_READING
                self.writeStatus += 1
                t = threading.Thread(target=self.runVMInfo, args=(vmName,username, password))
                t.start()
            return 0
        finally:
            self.lock.release()
    
    def runVMSInfo(self, username=None, password=None):
        logging.debug("ProxmoxManage: runVMSInfo(): instantiated")
        try:
            try:
                server = self.cf.getConfig()['PROXMOX']['VMANAGE_SERVER']
                port = self.cf.getConfig()['PROXMOX']['VMANAGE_APIPORT']
                nodename = self.cf.getConfig()['PROXMOX']['VMANAGE_NODE_NAME']
                proxapi = ProxmoxAPI(server, port=port, user=username, password=password, verify_ssl=False)
                
            except Exception:
                logging.error("Error in runConfigureVMNets(): An error occured when trying to connect to proxmox")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
                return None

            #clear out the current set
            self.tempVMs = {}
            self.readStatus = VMManage.MANAGER_READING

            try:
                allinfo = proxapi.cluster.resources.get(type='vm')
            except Exception:
                logging.error("Error in runVMSInfo: An error occured when trying to get cluster info")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)

            for vmiter in allinfo:
                # net info
                #GET UUID
                logging.debug("runVMSInfo(): adding 1 "+ str(self.writeStatus))
                vm = VM()
                vm.name = vmiter['name']
                vm.UUID = vmiter['vmid']
                if 'template' in vmiter:
                    vm.template = vmiter['template']
                else: 
                    vm.template = 0

                try:
                    netinfo = proxapi.nodes(nodename)('qemu')(vm.UUID)('config').get()
                except Exception:
                    logging.error("Error in <>(): An error occured when trying to get vm info")
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    traceback.print_exception(exc_type, exc_value, exc_traceback)

                # num interfaces
                nics = [value for key, value in netinfo.items() if 'net' in key.lower()]
                adaptorInfo = {}
                for nic in nics:
                    type=nic.split(',')[1].split("=")[0]
                    name=nic.split(',')[1].split("=")[1]
                    adaptorInfo[name] = type
                vm.adaptorInfo = adaptorInfo
                vm.state = vmiter['status']
                vm.groups = ""

                try:
                    #get latest snapshot
                    latest_snap = None
                    snaps = proxapi.nodes(nodename)('qemu')(vm.UUID )('snapshot').get()
                    for snap in snaps:
                        if 'parent' in snap and snap['name'] == 'current':
                            latest_snap = snap['parent']
                except Exception:
                    logging.error("Error in <>(): An error occured when trying to get vm info")
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    traceback.print_exception(exc_type, exc_value, exc_traceback)
                vm.latestSnapUUID = latest_snap
                self.tempVMs[vm.name] = vm
            try:
                self.lock.acquire()
                self.vms = self.tempVMs
            finally:
                self.lock.release()
            logging.debug("runVMSInfo(): completed")
        except Exception:
            logging.error("Error in runVMSInfo(): An error occured ")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
        finally:
            self.readStatus = VMManage.MANAGER_IDLE
            self.writeStatus -= 1
            logging.debug("runVMSInfo(): sub 1 "+ str(self.writeStatus))

    def runVMInfo(self, vmName, username=None, password=None):
        logging.debug("ProxmoxManage: runVMInfo(): instantiated")
        try:
            try:
                server = self.cf.getConfig()['PROXMOX']['VMANAGE_SERVER']
                port = self.cf.getConfig()['PROXMOX']['VMANAGE_APIPORT']
                nodename = self.cf.getConfig()['PROXMOX']['VMANAGE_NODE_NAME']
                proxapi = ProxmoxAPI(server, port=port, user=username, password=password, verify_ssl=False)
                
            except Exception:
                logging.error("Error in runConfigureVMNets(): An error occured when trying to connect to proxmox")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
                return None

            self.readStatus = VMManage.MANAGER_READING
            if vmName not in self.vms:
                logging.error("runVMInfo(): " + vmName + " not found in list of known vms: \r\n" + str(vmName))
                return -1
            
            try:
                allinfo = proxapi.cluster.resources.get(type='vm')
            except Exception:
                logging.error("Error in runVMSInfo: An error occured when trying to get cluster info")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)

            for vmiter in allinfo:
                if vmiter['name'] != vmName:
                    continue
                # net info
                #GET UUID
                logging.debug("runVMSInfo(): adding 1 "+ str(self.writeStatus))
                vm = VM()
                vm.name = vmiter['name']
                vm.UUID = vmiter['vmid']
                if 'template' in vmiter:
                    vm.template = vmiter['template']
                else: 
                    vm.template = 0

                try:
                    netinfo = proxapi.nodes(nodename)('qemu')(vm.UUID)('config').get()
                except Exception:
                    logging.error("Error in <>(): An error occured when trying to get vm info")
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    traceback.print_exception(exc_type, exc_value, exc_traceback)

                # num interfaces
                nics = [value for key, value in netinfo.items() if 'net' in key.lower()]
                adaptorInfo = {}
                for nic in nics:
                    type=nic.split(',')[1].split("=")[0]
                    name=nic.split(',')[1].split("=")[1]
                    adaptorInfo[name] = type
                vm.adaptorInfo = adaptorInfo
                vm.state = vmiter['status']
                vm.groups = ""

                try:
                    #get latest snapshot
                    latest_snap = None
                    snaps = proxapi.nodes(nodename)('qemu')(vm.UUID )('snapshot').get()
                    for snap in snaps:
                        if 'parent' in snap and snap['name'] == 'current':
                            latest_snap = snap['parent']
                except Exception:
                    logging.error("Error in <>(): An error occured when trying to get vm info")
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    traceback.print_exception(exc_type, exc_value, exc_traceback)
                vm.latestSnapUUID = latest_snap
                break
            try:
                self.lock.acquire()
                self.vms[vm.name] = vm
            finally:
                self.lock.release()
            logging.debug("runVMSInfo(): completed")
        except Exception:
            logging.error("Error in runVMSInfo(): An error occured ")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
        finally:
            self.readStatus = VMManage.MANAGER_IDLE
            self.writeStatus -= 1
            logging.debug("runVMSInfo(): sub 1 "+ str(self.writeStatus))

    def runConfigureVMNet(self, vmName, netNum, netName, username=None, password=None):
        try:
            logging.debug("runConfigureVMNet(): instantiated")
            self.readStatus = VMManage.MANAGER_READING
            logging.debug("runConfigureVMNet(): adding 1 "+ str(self.writeStatus))
            cloneNetNum = 1
            logging.debug("runConfigureVMNet(): Processing internal net names: " + str(netName))
            vmUUID = ""
            try:
                self.lock.acquire()
                vmUUID = str(self.vms[vmName].UUID)
            finally:
                self.lock.release()
            try:
                server = self.cf.getConfig()['PROXMOX']['VMANAGE_SERVER']
                port = self.cf.getConfig()['PROXMOX']['VMANAGE_APIPORT']
                nodename = self.cf.getConfig()['PROXMOX']['VMANAGE_NODE_NAME']
                proxapi = ProxmoxAPI(server, port=port, user=username, password=password, verify_ssl=False)
            except Exception:
                logging.error("Error in runConfigureVMNet(): An error occured when trying to connect to proxmox")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
                return None

            try:
                ifaces = proxapi.nodes(nodename)('network').get(type='bridge')
            except Exception:
                logging.error("Error in runConfigureVMNet(): An error occured when trying to get bridges")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)

            try:
                #create bridge if it doesn't exist
                res = proxapi.nodes(nodename)('network').post(iface=str(netName),node=nodename,type='bridge',autostart=1)
                self.basic_blocking_task_status(proxapi, res, nodename)
            except ResourceException:
                logging.warning("In runConfigureVMNet(): Interface may already exist: " + str(netName))
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
            try:
                res = proxapi.nodes(nodename)('network').put()
                self.basic_blocking_task_status(proxapi, res, nodename)
            except ResourceException:
                logging.error("In runConfigureVMNet(): error when trying to apply configuration update")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)

            #assign net to bridge
            kwargs = {f'net{netNum}': 'e1000,bridge='+str(netName)}
            try:
                logging.info("runConfigureVMNets(): Configuring Interface: " + str(vmUUID))
                res = proxapi.nodes(nodename)('qemu')(vmUUID)('config').post(**kwargs)
                self.basic_blocking_task_status(proxapi, res, nodename)
            except Exception:
                logging.error("Error in runConfigureVMNets(): An error occured when trying to configure vm network device")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
            logging.info("Command Output: "+ str(res))
            cloneNetNum += 1            
           
            logging.debug("runConfigureVMNets(): Thread completed")
        except Exception:
            logging.error("runConfigureVMNets() Error")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
        finally:
            self.readStatus = VMManage.MANAGER_IDLE
            self.writeStatus -= 1
            logging.debug("runConfigureVMNets(): sub 1 "+ str(self.writeStatus))


    def runRemoteCmds(self, cmds, username=None, password=None):
        logging.debug("ProxmoxManage: runRemoteCmds(): instantiated")
        try:
            self.readStatus = VMManage.MANAGER_READING
            logging.debug("runRemoteCmds(): adding 1 "+ str(self.writeStatus))

            try:
                server = self.cf.getConfig()['PROXMOX']['VMANAGE_SERVER']
                port = self.cf.getConfig()['PROXMOX']['VMANAGE_CMDPORT']
                nodename = self.cf.getConfig()['PROXMOX']['VMANAGE_NODE_NAME']
                proxssh = ssh_paramiko.SshParamikoSession(server,port=port, user=username,password=password)
            except Exception:
                logging.error("Error in runConfigureVMNet(): An error occured when trying to connect to proxmox")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
                return None
            cmdNum = 1
            for cmd in cmds:
                logging.info("runRemoteCmds(): Running cmd # " + str(cmdNum) + " of " + str(len(cmds)) + ": " + str(cmd))
                res = proxssh._exec(shlex.split(cmd))
                logging.info("runRemoteCmds(): Command completed: " + str(res))
            logging.debug("runRemoteCmds(): Thread completed")
        except Exception:
            logging.error("runRemoteCmds() Error: " + " cmd: " + cmd)
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
        finally:
            self.readStatus = VMManage.MANAGER_IDLE
            self.writeStatus -= 1
            logging.debug("runRemoteCmds(): sub 1 "+ str(self.writeStatus))

    def getVMStatus(self, vmName, username=None, password=None):
        logging.debug("ProxmoxManage: getVMStatus(): instantiated " + vmName)
        exists = False
        try:
            self.lock.acquire()
            exists = vmName in self.vms
            if not exists:
                logging.error("getVMStatus(): " + vmName + " not found in list of known vms: \r\n" + str(vmName))
                return -1
            resVM = self.vms[vmName]
            #Don't want to rely on python objects in case we go with 3rd party clients in the future
            return {"vmName" : resVM.name, "vmUUID" : resVM.UUID, "setupStatus" : resVM.setupStatus, "vmState" : resVM.state, "adaptorInfo" : resVM.adaptorInfo, "groups" : resVM.groups, "latestSnapUUID": resVM.latestSnapUUID}
        finally:
            self.lock.release()        
        
    def getManagerStatus(self):
        logging.debug("ProxmoxManage: getManagerStatus(): instantiated")
        vmStatus = {}
        try:
            self.lock.acquire()
            for vmName in self.vms:
                resVM = self.vms[vmName]
                vmStatus[resVM.name] = {"vmUUID" : resVM.UUID, "setupStatus" : resVM.setupStatus, "vmState" : resVM.state, "adaptorInfo" : resVM.adaptorInfo, "groups" : resVM.groups}
        finally:
            self.lock.release()
        
        return {"readStatus" : self.readStatus, "writeStatus" : self.writeStatus, "vmstatus" : vmStatus}

    def importVM(self, filepath, username=None, password=None):
        logging.debug("ProxmoxManage: importVM(): instantiated")
        cmd = "import \"" + filepath + "\" --options keepallmacs"
        self.readStatus = VMManage.MANAGER_READING
        self.writeStatus += 1
        t = threading.Thread(target=self.runRemoteCmds, args=([cmd],username, password))
        t.start()
        return 0  

    def snapshotVM(self, vmName, username=None, password=None):
        logging.debug("ProxmoxManage: snapshotVM(): instantiated")
        try:
            self.readStatus = VMManage.MANAGER_READING
            self.writeStatus += 1
            exists = vmName in self.vms
            if not exists:
                logging.error("snapshotVM(): " + vmName + " not found in list of known vms: \r\n" + str(vmName))
                return -1
            vmUUID = str(self.vms[vmName].UUID)
            logging.debug("snapshotVM(): adding 1 "+ str(self.writeStatus))
            
            try:
                server = self.cf.getConfig()['PROXMOX']['VMANAGE_SERVER']
                port = self.cf.getConfig()['PROXMOX']['VMANAGE_APIPORT']
                nodename = self.cf.getConfig()['PROXMOX']['VMANAGE_NODE_NAME']
                proxapi = ProxmoxAPI(server, port=port, user=username, password=password, verify_ssl=False)
            except Exception:
                logging.error("Error in runConfigureVMNet(): An error occured when trying to connect to proxmox")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
                return None

            try:
                #get latest snapshot
                snapname = "s"+str(int(time.time()))
                res = proxapi.nodes(nodename)('qemu')(vmUUID)('snapshot').post(snapname=snapname, vmstate=1)
                self.basic_blocking_task_status(proxapi, res, nodename)
                logging.info("snapshotVM(): Snapshot created: " + snapname + " " + str(res))
            except Exception:
                logging.error("Error in snapshotVM(): An error occured when trying to create snapshot "+snapname+" -- perhaps it doesn't exist")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)

            logging.debug("snapshotVM(): Thread completed")
        except Exception:
            logging.error("snapshotVM() Error.")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
        finally:
            self.readStatus = VMManage.MANAGER_IDLE
            self.writeStatus -= 1
            logging.debug("snapshotVM(): sub 1 "+ str(self.writeStatus))

    def exportVM(self, vmName, filepath, username=None, password=None):
        logging.debug("ProxmoxManage: exportVM(): instantiated")
        #first remove any quotes that may have been entered before (because we will add some after we add the file and extension)
        try:
            self.lock.acquire()
            exists = vmName in self.vms
            if not exists:
                logging.error("exportVM(): " + vmName + " not found in list of known vms: \r\n" + str(vmName))
                return -1
            filepath = filepath.replace("\"","")
            exportfilename = os.path.join(filepath,vmName+".ova")
            cmd = "export " + self.vms[vmName].UUID + " -o \"" + exportfilename# + "\" --iso"
            self.readStatus = VMManage.MANAGER_READING
            self.writeStatus += 1
            t = threading.Thread(target=self.runRemoteCmds, args=([cmd],username, password))
            t.start()
            return 0
        finally:
            self.lock.release()

    def startVM(self, vmName, username=None, password=None):
        logging.debug("ProxmoxManage: startVM(): instantiated")
        try:
            self.readStatus = VMManage.MANAGER_READING
            self.writeStatus += 1
            exists = vmName in self.vms
            if not exists:
                logging.error("startVM(): " + vmName + " not found in list of known vms: \r\n" + str(vmName))
                return -1
            vmUUID = str(self.vms[vmName].UUID)
            logging.debug("startVM(): adding 1 "+ str(self.writeStatus))
            
            try:
                server = self.cf.getConfig()['PROXMOX']['VMANAGE_SERVER']
                port = self.cf.getConfig()['PROXMOX']['VMANAGE_APIPORT']
                nodename = self.cf.getConfig()['PROXMOX']['VMANAGE_NODE_NAME']
                proxapi = ProxmoxAPI(server, port=port, user=username, password=password, verify_ssl=False)
            except Exception:
                logging.error("Error in startVM(): An error occured when trying to connect to proxmox")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
                return None

            try:
                res = proxapi.nodes(nodename)('qemu')(vmUUID)('status')('start').post()
                self.basic_blocking_task_status(proxapi, res, nodename)
            except Exception:
                logging.error("Error in startVM(): An error occured when trying to start vm "+str(vmUUID)+" -- perhaps it doesn't exist")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)


            logging.debug("startVM(): Thread completed")
        except Exception:
            logging.error("startVM() Error.")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
        finally:
            self.readStatus = VMManage.MANAGER_IDLE
            self.writeStatus -= 1
            logging.debug("startVM(): sub 1 "+ str(self.writeStatus))


    def pauseVM(self, vmName, username=None, password=None):
        logging.debug("ProxmoxManage: pauseVM(): instantiated")
        try:
            self.readStatus = VMManage.MANAGER_READING
            self.writeStatus += 1
            exists = vmName in self.vms
            if not exists:
                logging.error("pauseVM(): " + vmName + " not found in list of known vms: \r\n" + str(vmName))
                return -1
            vmUUID = str(self.vms[vmName].UUID)
            logging.debug("pauseVM(): adding 1 "+ str(self.writeStatus))
            
            try:
                server = self.cf.getConfig()['PROXMOX']['VMANAGE_SERVER']
                port = self.cf.getConfig()['PROXMOX']['VMANAGE_APIPORT']
                nodename = self.cf.getConfig()['PROXMOX']['VMANAGE_NODE_NAME']
                proxapi = ProxmoxAPI(server, port=port, user=username, password=password, verify_ssl=False)
            except Exception:
                logging.error("Error in pauseVM(): An error occured when trying to connect to proxmox")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
                return None

            try:
                res = proxapi.nodes(nodename)('qemu')(vmUUID)('status')('suspend').post()
                self.basic_blocking_task_status(proxapi, res, nodename)
            except Exception:
                logging.error("Error in pauseVM(): An error occured when trying to start vm "+str(vmUUID)+" -- perhaps it doesn't exist")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)


            logging.debug("pauseVM(): Thread completed")
        except Exception:
            logging.error("pauseVM() Error.")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
        finally:
            self.readStatus = VMManage.MANAGER_IDLE
            self.writeStatus -= 1
            logging.debug("pauseVM(): sub 1 "+ str(self.writeStatus))

    def suspendVM(self, vmName, username=None, password=None):
        logging.debug("ProxmoxManage: suspendVM(): instantiated")
        try:
            self.readStatus = VMManage.MANAGER_READING
            self.writeStatus += 1
            exists = vmName in self.vms
            if not exists:
                logging.error("suspendVM(): " + vmName + " not found in list of known vms: \r\n" + str(vmName))
                return -1
            vmUUID = str(self.vms[vmName].UUID)
            logging.debug("suspendVM(): adding 1 "+ str(self.writeStatus))
            
            try:
                server = self.cf.getConfig()['PROXMOX']['VMANAGE_SERVER']
                port = self.cf.getConfig()['PROXMOX']['VMANAGE_APIPORT']
                nodename = self.cf.getConfig()['PROXMOX']['VMANAGE_NODE_NAME']
                proxapi = ProxmoxAPI(server, port=port, user=username, password=password, verify_ssl=False)
            except Exception:
                logging.error("Error in suspendVM(): An error occured when trying to connect to proxmox")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
                return None

            try:
                res = proxapi.nodes(nodename)('qemu')(vmUUID)('status')('suspend').post(todisk=1)
                self.basic_blocking_task_status(proxapi, res, nodename)
            except Exception:
                logging.error("Error in suspendVM(): An error occured when trying to start vm "+str(vmUUID)+" -- perhaps it doesn't exist")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)

            logging.debug("suspendVM(): Thread completed")
        except Exception:
            logging.error("suspendVM() Error.")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
        finally:
            self.readStatus = VMManage.MANAGER_IDLE
            self.writeStatus -= 1
            logging.debug("suspendVM(): sub 1 "+ str(self.writeStatus))

    def stopVM(self, vmName, username=None, password=None):
        logging.debug("ProxmoxManage: stopVM(): instantiated")
        try:
            self.readStatus = VMManage.MANAGER_READING
            self.writeStatus += 1
            exists = vmName in self.vms
            if not exists:
                logging.error("stopVM(): " + vmName + " not found in list of known vms: \r\n" + str(vmName))
                return -1
            vmUUID = str(self.vms[vmName].UUID)
            logging.debug("stopVM(): adding 1 "+ str(self.writeStatus))
            
            try:
                server = self.cf.getConfig()['PROXMOX']['VMANAGE_SERVER']
                port = self.cf.getConfig()['PROXMOX']['VMANAGE_APIPORT']
                nodename = self.cf.getConfig()['PROXMOX']['VMANAGE_NODE_NAME']
                proxapi = ProxmoxAPI(server, port=port, user=username, password=password, verify_ssl=False)
            except Exception:
                logging.error("Error in stopVM(): An error occured when trying to connect to proxmox")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
                return None

            try:
                res = proxapi.nodes(nodename)('qemu')(vmUUID)('status')('stop').post()
                self.basic_blocking_task_status(proxapi, res, nodename)
            except Exception:
                logging.error("Error in stopVM(): An error occured when trying to start vm "+str(vmUUID)+" -- perhaps it doesn't exist")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)

            logging.debug("stopVM(): Thread completed")
        except Exception:
            logging.error("stopVM() Error.")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
        finally:
            self.readStatus = VMManage.MANAGER_IDLE
            self.writeStatus -= 1
            logging.debug("stopVM(): sub 1 "+ str(self.writeStatus))

    def removeVM(self, vmName, username=None, password=None):
        logging.debug("ProxmoxManage: removeVM(): instantiated")
        #check to make sure the vm is known, if not should refresh or check name:
        try:
            self.lock.acquire()
            exists = vmName in self.vms
            if not exists:
                logging.error("removeVM(): " + vmName + " not found in list of known vms: \r\n" + str(vmName))
                return -1
            self.readStatus = VMManage.MANAGER_READING
            self.writeStatus += 1
            t = threading.Thread(target=self.runRemoveVM, args=(vmName, str(self.vms[vmName].UUID), username, password))
            t.start()
            return 0
        finally:
            self.lock.release()

    def runRemoveVM(self, vmName, vmUUID, username=None, password=None):
        logging.debug("ProxmoxManage: runRemoveVM(): instantiated")
        try:
            self.readStatus = VMManage.MANAGER_READING
            logging.debug("runRemoveVM(): adding 1 "+ str(self.writeStatus))
            exists = vmName in self.vms
            if not exists:
                logging.error("runRemoveVM(): " + vmName + " not found in list of known vms: \r\n" + str(vmName))
                return -1
            vmUUID = str(self.vms[vmName].UUID)
            logging.debug("runRemoveVM(): adding 1 "+ str(self.writeStatus))
            
            try:
                server = self.cf.getConfig()['PROXMOX']['VMANAGE_SERVER']
                port = self.cf.getConfig()['PROXMOX']['VMANAGE_APIPORT']
                nodename = self.cf.getConfig()['PROXMOX']['VMANAGE_NODE_NAME']
                proxapi = ProxmoxAPI(server, port=port, user=username, password=password, verify_ssl=False)
            except Exception:
                logging.error("Error in runRemoveVM(): An error occured when trying to connect to proxmox")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
                return None

            try:
                proxapi.nodes(nodename)('qemu')(vmUUID).delete(node=nodename, vmid=vmUUID)
                success = True
            except Exception:
                print("Error in runRemoveVM(): An error occured when trying to delete vm "+str(vmUUID)+" -- perhaps it doesn't exist")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
            if success:
                try:
                    self.lock.acquire()
                    del self.vms[vmName]
                finally:
                    self.lock.release()

            logging.debug("runRemoveVM(): Thread completed")
        except Exception:
            logging.error("runRemoveVM() Error.")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
        finally:
            self.readStatus = VMManage.MANAGER_IDLE
            self.writeStatus -= 1
            logging.debug("runRemoveVM(): sub 1 "+ str(self.writeStatus))

    def cloneVMConfigAll(self, vmName, cloneName, cloneSnapshots, linkedClones, groupName, internalNets, vrdpPort, refreshVMInfo=False, username=None, password=None):
        logging.debug("ProxmoxManage: cloneVMConfigAll(): instantiated")
        #check to make sure the vm is known, if not should refresh or check name:
        try:
            self.lock.acquire()
            exists = vmName in self.vms
            if not exists:
                logging.error("cloneVMConfigAll(): " + vmName + " not found in list of known vms: \r\n" + str(self.vms))
                return -1
        finally:
            self.lock.release()

        if refreshVMInfo == True:
            self.readStatus = VMManage.MANAGER_READING
            self.writeStatus += 1
            #runVMInfo obtains it's own lock
            self.runVMInfo(vmName, username, password)
        self.readStatus = VMManage.MANAGER_READING
        self.writeStatus += 1
        t = threading.Thread(target=self.runCloneVMConfigAll, args=(vmName, cloneName, cloneSnapshots, linkedClones, groupName, internalNets, vrdpPort, username, password))
        t.start()
        return 0

    def runCloneVMConfigAll(self, vmName, cloneName, cloneSnapshots, linkedClones, groupName, internalNets, vrdpPort, username=None, password=None):
        logging.debug("ProxmoxManage: runCloneVMConfigAll(): instantiated")
        try:
            self.readStatus = VMManage.MANAGER_READING
            logging.debug("runCloneVMConfigAll(): adding 1 "+ str(self.writeStatus))
            #first clone
            #Check that vm does exist
            try:
                self.lock.acquire()
                exists = vmName in self.vms
                if not exists:
                    logging.error("runCloneVMConfigAll(): " + vmName + " not found in list of known vms: \r\n" + str(vmName))
                    return
            finally:
                self.lock.release()
            # clone the VM
            self.writeStatus += 1
            self.runCloneVM(vmName, cloneName, cloneSnapshots, linkedClones, groupName, username, password)
            
            #netsetup
            try:
                self.lock.acquire()
                exists = cloneName in self.vms
                if not exists:
                    logging.error("runCloneVMConfigAll(): " + cloneName + " not found in list of known vms: \r\n" + str(cloneName))
                    return
                else:
                    cloneUUID = str(self.vms[cloneName].UUID)
            finally:
                self.lock.release()

            self.writeStatus += 1
            self.runConfigureVMNets(cloneName, internalNets, username, password)

            #vrdp setup (if applicable)
            if vrdpPort != None:
                self.writeStatus += 1
                self.runEnableVRDP(cloneName, vrdpPort, username, password)
            
            #create snap
            self.snapshotVM(cloneName, username, password)
            logging.debug("runCloneVMConfigAll(): Thread completed")

        except Exception:
            logging.error("runCloneVMConfigAll(): Error in runCloneVMConfigAll(): An error occured ")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
        finally:
            self.readStatus = VMManage.MANAGER_IDLE
            self.writeStatus -= 1
            logging.debug("runCloneVMConfigAll(): sub 1 "+ str(self.writeStatus))

    def cloneVM(self, vmName, cloneName, cloneSnapshots, linkedClones=True, groupName=None, refreshVMInfo=True, username=None, password=None):
        logging.debug("ProxmoxManage: cloneVM(): instantiated")
        #check to make sure the vm is known, if not should refresh or check name:
        try:
            self.lock.acquire()
            exists = vmName in self.vms
            if not exists:
                logging.error("cloneVM(): " + vmName + " not found in list of known vms: \r\n" + str(self.vms))
                return -1
        finally:
            self.lock.release()

        if refreshVMInfo == True:
            self.readStatus = VMManage.MANAGER_READING
            self.writeStatus += 1
            #runVMInfo obtains it's own lock
            self.runVMInfo(vmName, username, password)
        self.readStatus = VMManage.MANAGER_READING
        self.writeStatus += 1
        t = threading.Thread(target=self.runCloneVM, args=(vmName, cloneName, cloneSnapshots, linkedClones, groupName, username, password))
        t.start()
        return 0

    def runCloneVM(self, vmName, cloneName, cloneSnapshots=None, linkedClones=None, groupName=None, username=None, password=None):
        logging.debug("ProxmoxManage: runCloneVM(): instantiated")
        try:
            self.readStatus = VMManage.MANAGER_READING
            logging.debug("runCloneVM(): adding 1 "+ str(self.writeStatus))
            #First check that the clone doesn't exist:
            try:
                self.lock.acquire()
                exists = cloneName in self.vms
                if exists:
                    logging.error("runCloneVM(): A VM with the clone name already exists and is registered... skipping " + str(cloneName))
                    return
            finally:
                self.lock.release()

            vmUUID = str(self.vms[vmName].UUID)
            logging.debug("runCloneVM(): adding 1 "+ str(self.writeStatus))
            
            try:
                server = self.cf.getConfig()['PROXMOX']['VMANAGE_SERVER']
                port = self.cf.getConfig()['PROXMOX']['VMANAGE_APIPORT']
                nodename = self.cf.getConfig()['PROXMOX']['VMANAGE_NODE_NAME']
                proxapi = ProxmoxAPI(server, port=port, user=username, password=password, verify_ssl=False)
            except Exception:
                logging.error("Error in runRemoveVM(): An error occured when trying to connect to proxmox")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
                return None

            #get id from name
            #check if vm is a template already, if not, make it one
            if self.vms[vmName].template == None:
                istemplate = 0
            else:
                istemplate = self.vms[vmName].template
            #convert to template (to allow linked clones)
            if istemplate == 0:
                try:
                    res = proxapi.nodes(nodename)('qemu')(vmUUID)('template').post()
                    self.basic_blocking_task_status(proxapi, res, nodename)
                    self.vms[vmName].template = 1
                    logging.info("runCloneVM(): Completed setting vm to template: " + str(res))
                except Exception:
                    print("Error in <>(): An error occured when trying set vm to template")
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    traceback.print_exception(exc_type, exc_value, exc_traceback)
                    exit -1

            #get next free vmid
            try:
                newid = proxapi.cluster('nextid').get()
                logging.info("runCloneVM(): Retrieved next available vm id: " + str(newid))
            except Exception:
                print("Error in runCloneVM(): An error occured when trying to get a new vm id")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
                exit -1

            #now issue the create clone command
            try:
                res = proxapi.nodes(nodename)('qemu')(vmUUID)('clone').post(name=cloneName, newid=newid, full=0)
                self.basic_blocking_task_status(proxapi, res, nodename)
                logging.info("runCloneVM(): Clone created: " + str(res))
            except Exception:
                print("Error in <>(): An error occured when trying to set clone vm")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
            # once it's a template, I don't think there's a way back... so we'll just leave it as a template for now
            # try:
            #     res = proxapi.nodes(nodename)('qemu')(vmUUID)('config').post(template=0)
            #     self.basic_blocking_task_status(proxapi, res, nodename)
            #     logging.info("runCloneVM(): Completed setting vm to non-template mode: " + str(res))
            # except Exception:
            #     print("Error in runCloneVM An error occured when trying to set vm to non-template mode")
            #     exc_type, exc_value, exc_traceback = sys.exc_info()
            #     traceback.print_exception(exc_type, exc_value, exc_traceback)
            self.writeStatus += 1
            #just add to self.vms if it's not there and then call the vminfo
            self.runVMInfo(cloneName, username, password)

        except Exception:
            logging.error("runCloneVM(): Error in runCloneVM(): An error occured; it could be due to a missing snapshot for the VM")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
        finally:
            self.readStatus = VMManage.MANAGER_IDLE
            self.writeStatus -= 1
            logging.debug("runCloneVM(): sub 1 "+ str(self.writeStatus))

    def enableVRDPVM(self, vmName, vrdpPort, username=None, password=None):
        logging.debug("ProxmoxManage: enabledVRDP(): instantiated")
        #check to make sure the vm is known, if not should refresh or check name:
        try:
            self.lock.acquire()
            exists = vmName in self.vms
            if not exists:
                logging.error("enabledVRDP(): " + vmName + " not found in list of known vms: \r\n" + str(self.vms))
                return -1
        finally:
            self.lock.release()

        self.readStatus = VMManage.MANAGER_READING
        self.writeStatus += 1
        t = threading.Thread(target=self.runEnableVRDP, args=(vmName, vrdpPort, username, password))
        t.start()
        return 0

    def runEnableVRDP(self, vmName, vrdpPort, username=None, password=None):
        logging.debug("ProxmoxManage: runEnableVRDP(): instantiated")
        #check to make sure the vm is known, if not should refresh or check name:
        try:
            self.lock.acquire()
            exists = vmName in self.vms
            if not exists:
                logging.error("enabledVRDP(): " + vmName + " not found in list of known vms: \r\n" + str(self.vms))
                return -1

            self.readStatus = VMManage.MANAGER_READING
            logging.debug("runEnableVRDP(): adding 1 "+ str(self.writeStatus))

            logging.debug("runEnableVRDP(): Processing restore latest snapshot for: " + str(vmName))
            vmUUID = ""
            vmUUID = str(self.vms[vmName].UUID)

        finally:
            self.lock.release()       
        try:
            #add vnc port to config file            
            vncport = int(vrdpPort) - 5900
            cmd = 'sed -i "$ a args: -vnc 0.0.0.0:'+str(vncport)+'" /etc/pve/qemu-server/' + str(vmUUID) + '.conf'
            self.readStatus = VMManage.MANAGER_READING
            self.writeStatus += 1
            t = threading.Thread(target=self.runRemoteCmds, args=([cmd],username, password))
            t.start()
            return 0  

        except Exception:
            logging.error("runEnableVRDP(): Error in runEnableVRDP(): An error occured ")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
        finally:
            self.readStatus = VMManage.MANAGER_IDLE
            self.writeStatus -= 1
            logging.debug("runEnableVRDP(): sub 1 "+ str(self.writeStatus))

    def runRestoreLatestSnapVM(self, vmName, username=None, password=None):
        logging.debug("ProxmoxManage: runRestoreLatestSnapVM(): instantiated")
        try:
            logging.debug("runRestoreLatestSnapVM(): instantiated")
            self.readStatus = VMManage.MANAGER_READING
            logging.debug("runRestoreLatestSnapVM(): adding 1 "+ str(self.writeStatus))

            logging.debug("runRestoreLatestSnapVM(): Processing restore latest snapshot for: " + str(vmName))
            vmUUID = ""
            try:
                self.lock.acquire()
                vmUUID = str(self.vms[vmName].UUID)
            finally:
                self.lock.release()
            try:
                server = self.cf.getConfig()['PROXMOX']['VMANAGE_SERVER']
                port = self.cf.getConfig()['PROXMOX']['VMANAGE_APIPORT']
                nodename = self.cf.getConfig()['PROXMOX']['VMANAGE_NODE_NAME']
                proxapi = ProxmoxAPI(server, port=port, user=username, password=password, verify_ssl=False)
            except Exception:
                logging.error("Error in runRestoreLatestSnapVM(): An error occured when trying to connect to proxmox")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
                return None
            
            ########Revert to Snapshot clone
            try:
                #get latest snapshot
                latest_snap = None
                snaps = proxapi.nodes(nodename)('qemu')(vmUUID)('snapshot').get()
                for snap in snaps:
                    if 'parent' in snap and snap['name'] == 'current':
                        latest_snap = snap['parent']

                #restore latest snapshot
                if latest_snap != None:
                    res = proxapi.nodes(nodename)('qemu')(vmUUID)('snapshot')(latest_snap)('rollback').post(start='0')
                    self.basic_blocking_task_status(proxapi, res, nodename)
                else:
                    Exception
                    
            except Exception:
                print("Error in runRestoreLatestSnapVM(): An error occured when trying to revert snapshot vm "+str(vmUUID)+" -- perhaps it doesn't exist")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)

        except Exception:
            logging.error("runRestoreLatestSnapVM(): Error in runRestoreLatestSnapVM(): An error occured ")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
        finally:
            self.readStatus = VMManage.MANAGER_IDLE
            self.writeStatus -= 1
            logging.debug("runRestoreLatestSnapVM(): sub 1 "+ str(self.writeStatus))

    def restoreLatestSnapVM(self, vmName, username=None, password=None):
        logging.debug("ProxmoxManage: restoreLatestSnapVM(): instantiated")
        #check to make sure the vm is known, if not should refresh or check name:
        try:
            self.lock.acquire()
            exists = vmName in self.vms
            if not exists:
                logging.error("restoreLatestSnapVM(): " + vmName + " not found in list of known vms: \r\n" + str(self.vms))
                return -1
            cmd = "snapshot " + str(self.vms[vmName].UUID) + " restorecurrent"
            self.readStatus = VMManage.MANAGER_READING
            self.writeStatus += 1
            t = threading.Thread(target=self.runRestoreLatestSnapVM, args=(vmName,username,password))
            t.start()
            return 0
        finally:
            self.lock.release()
