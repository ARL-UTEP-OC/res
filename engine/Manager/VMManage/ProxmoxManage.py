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
from engine.Configuration.ExperimentConfigIO import ExperimentConfigIO
from threading import RLock
from proxmoxer import ProxmoxAPI
from proxmoxer.core import ResourceException
from proxmoxer.backends import ssh_paramiko
from proxmoxer.tools import Tasks
import random

class ProxmoxManage(VMManage):
    def __init__(self, initializeVMManage=False, username=None, password=None):
        logging.debug("ProxmoxManage.__init__(): instantiated")
        VMManage.__init__(self)
        self.cf = SystemConfigIO()
        self.eco = ExperimentConfigIO.getInstance()
        # A lock for acces/updates to self.vms
        self.lock = RLock()
        self.vms = {}
        self.tempVMs = {}
        self.proxapi = None
        self.proxssh = None
        self.sshusername = None
        self.sshpassword = None
        self.initialized = False
        if username != None and password != None and username.strip() != "" and password.strip() != "":
            self.setRemoteCreds(initializeVMManage, username, password)
            
    def isInitialized(self):
        logging.debug("ProxmoxManage: isInitialized(): instantiated")
        return self.initialized

    def setRemoteCreds(self, refresh=False, username=None, password=None):
        logging.info("ProxmoxManage.setRemoteCreds(): Initializing ProxmoxManage; collecting VM information...")
        if username != None and password != None and username.strip() != "" and password.strip() != "" and len(username) > 4:
            self.proxapi = self.getProxAPI(username=username, password=password)
            sshuser = username[:-4]
            self.proxssh = self.getProxSSH(username=sshuser, password=password)
            if refresh:
                self.refreshAllVMInfo()
                result = self.getManagerStatus()["writeStatus"]
                while result != self.MANAGER_IDLE:
                #waiting for manager to finish query...
                    result = self.getManagerStatus()["writeStatus"]
                    time.sleep(.1)
                self.initialized = True
        logging.info("ProxmoxManage.setRemoteCreds(): Done...")

    def getProxAPI(self, username=None, password=None):
        logging.debug("ProxmoxManage: getProxAPI(): instantiated")
        try:
            #instead get this from experiment config file
            port = self.cf.getConfig()['PROXMOX']['VMANAGE_APIPORT']
            server = self.cf.getConfig()['PROXMOX']['VMANAGE_SERVER']
            # vmHostname, vmserversshport, rdiplayhostname, chatserver, challengesserver, users_file = self.eco.getExperimentServerInfo(configname)
            # server = vmHostname

            # splithostname = vmHostname.split("://")
            # if len(splithostname) > 1:
            #     rsplit = splithostname[1]
            #     if len(rsplit.split(":")) > 1:
            #         port = rsplit.split(":")[1].split("/")[0]
            #     server = rsplit.split("/")[0]

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

    def getProxSSH(self, username=None, password=None):
        logging.debug("ProxmoxManage: getProxSSH(): instantiated")
        try:
            port = self.cf.getConfig()['PROXMOX']['VMANAGE_CMDPORT']
            server = self.cf.getConfig()['PROXMOX']['VMANAGE_SERVER']
            
            # vmHostname, vmserversshport, rdisplayhostname, chatserver, challengesserver, users_file = self.eco.getExperimentServerInfo(configname)
            # server = vmHostname            
            # splithostname = vmHostname.split("://")
            # if len(splithostname) > 1:
            #     rsplit = splithostname[1]
            #     server = rsplit.split("/")[0]
            if self.proxssh == None and username != None and password != None and username.strip() != "" and password.strip() != "":
                self.proxssh = ssh_paramiko.SshParamikoSession(server,port=port, user=username,password=password)
                self.sshusername = username
                self.sshpassword = password
            elif self.proxssh != None and username != None and password != None and username.strip() != "" and password.strip() != "":
                self.proxssh = None
                self.proxssh = ssh_paramiko.SshParamikoSession(server,port=port, user=username,password=password)
                self.sshusername = username
                self.sshpassword = password
            return self.proxssh
        except Exception:
            logging.error("Error in getProxSSH(): An error occured when trying to connect to proxmox with ssh")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
            self.proxssh = None
            return None

    def checkVMExistsRetry(self, vmName, caller, retryMax=1, sleeptime=.1):
        logging.debug("ProxmoxManage: checkVMExistsRetry(): instantiated")
        #TODO: check if locked instead
        #Check that vm does exist
        retry =1
        exists = vmName in self.vms
        while exists == False:
            logging.error(caller + "(): " + vmName + " not found in list of known vms: \r\n" + str(vmName) + " retrying attempt " + str(retry) + " of " + str(retryMax))
            if retry < retryMax:
                time.sleep(sleeptime)
                retry += 1
                exists = vmName in self.vms
            else:
                logging.error(caller + "(): " + vmName + " not found in list of known vms: \r\n" + str(vmName) + " giving up")
                return -1
        return 0

    def basic_blocking_task_status(self, proxmox_api, task_id, caller=""):
        logging.debug("ProxmoxManage: basic_blocking_task_status(): instantiated by " + str(caller))
        Tasks.blocking_status(proxmox_api, task_id)

    def configureVMNet(self, vmName, netNum, netName, username=None, password=None):
        logging.debug("ProxmoxManage: configureVMNet(): instantiated")
        #check to make sure the vm is known, if not should refresh or check name:
        if self.checkVMExistsRetry(vmName, "configureVMNet") == -1:
            return -1

        self.readStatus = VMManage.MANAGER_READING
        self.writeStatus += 1
        t = threading.Thread(target=self.runConfigureVMNet, args=(vmName, netNum, netName, username, password))
        t.start()
        return 0

    def configureVMNets(self, vmName, internalNets, username=None, password=None):
        logging.debug("ProxmoxManage: configureVMNets(): instantiated")
        #check to make sure the vm is known, if not should refresh or check name:
        if self.checkVMExistsRetry(vmName, "configureVMNets") == -1:
            return -1

        self.readStatus = VMManage.MANAGER_READING
        self.writeStatus += 1
        t = threading.Thread(target=self.runConfigureVMNets, args=(vmName, internalNets, username, password))
        t.start()
        return 0

    def runConfigureVMNets(self, vmName, internalNets, username=None, password=None, refreshNetwork=False):
        try:
            logging.debug("runConfigureVMNets(): instantiated")
            self.readStatus = VMManage.MANAGER_READING
            cloneNetNum = 0
            logging.debug("runConfigureVMNets(): Processing internal net names: " + str(internalNets))
            vmUUID = ""
            vmUUID = str(self.vms[vmName].UUID)
            createdNets = []
            try:
                nodename = self.cf.getConfig()['PROXMOX']['VMANAGE_NODE_NAME']
                proxapi = self.getProxAPI(username, password)
                if proxapi == None:
                    return None
            except Exception:
                #logging.error("Error in <>(): An error occured ")
                logging.error("Error in runConfigureVMNets(): An error occured when trying to connect to proxmox")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
                return None

            for internalnet in internalNets:
                try:
                    ifaces_ds = proxapi.nodes(nodename)('network').get(type='bridge')
                    ifaces = []
                    for iface in ifaces_ds:
                        ifaces.append(iface['iface'])
                except Exception:
                    #logging.error("Error in <>(): An error occured ")
                    logging.error("Error in runConfigureVMNets(): An error occured when trying to get bridges")
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    traceback.print_exception(exc_type, exc_value, exc_traceback)

                try:
                    #create bridge if it doesn't exist
                    if internalnet not in ifaces and internalnet not in createdNets:
                        res = proxapi.nodes(nodename)('network').post(iface=str(internalnet),node=nodename,type='bridge',autostart=1)
                        if res == None:
                            createdNets.append(internalnet)
                    # self.basic_blocking_task_status(proxapi, res, 'bridge-create')
                except ResourceException:
                    logging.warning("runConfigureVMNets(): interface may already exist: " + str(internalnet))
                    # exc_type, exc_value, exc_traceback = sys.exc_info()
                    # traceback.print_exception(exc_type, exc_value, exc_traceback)

                #assign net to bridge
                kwargs = {f'net{cloneNetNum}': 'e1000,bridge='+str(internalnet)}
                # kwargs = {f'net{cloneNetNum}': 'virtio,bridge='+str(internalnet)}
                try:
                    logging.info("runConfigureVMNets(): Configuring Interface for VMID: " + str(vmUUID))
                    res = proxapi.nodes(nodename)('qemu')(vmUUID)('config').post(**kwargs)
                    self.basic_blocking_task_status(proxapi, res, 'config')
                except Exception:
                    logging.error("Error in runConfigureVMNets(): An error occured when trying to configure vm network device")
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    traceback.print_exception(exc_type, exc_value, exc_traceback)
                cloneNetNum += 1        
            if refreshNetwork:    
                self.refreshNetwork()
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
        # if self.checkVMExistsRetry(vmName, "guestCommands") == -1:
        #     return -1
        #  self.guestThreadStatus += 1
        #  t = threading.Thread(target=self.runGuestCommands, args=(vmName, cmds, delay, username, password))
        #  t.start()
        #  return 0

    def runGuestCommands(self, vmName, cmds, delay, username=None, password=None):
        logging.debug("ProxmoxManage: runGuestCommands(): instantiated")
        # try:
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
        res = self.checkVMExistsRetry(vmName, "refreshVMInfo",sleeptime=.1)
        #TODO: change this only look at 1 vpm, not all!!
        if res == -1:
            logging.warning("refreshVMInfo(): " + vmName + " not found in list of known vms... refreshing\r\n")
            #TODO: CHECKING IF THIS WILL WORK
            t = threading.Thread(target=self.runVMInfo, args=(vmName, username, password))
            self.readStatus = VMManage.MANAGER_READING
            self.writeStatus += 1
            t.start()
        else:
            self.readStatus = VMManage.MANAGER_READING
            self.writeStatus += 1
            t = threading.Thread(target=self.runVMInfo, args=(vmName, username, password))
            t.start()
        return 0
    
    def runVMSInfo(self, username=None, password=None):
        logging.debug("ProxmoxManage: runVMSInfo(): instantiated")
        print("Refreshing all vms")
        try:
            try:
                nodename = self.cf.getConfig()['PROXMOX']['VMANAGE_NODE_NAME']
                proxapi = self.getProxAPI(username, password)
                if proxapi == None:
                    return None
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
            vm = None
            if allinfo is None:
                logging.error("runVMSInfo(): info is None")
                return -1

            for vmiter in allinfo:
                # net info
                if vmiter['node'] != nodename:
                    continue
                #GET UUID
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

    def runVMInfo(self, vmName, username=None, password=None, vmid=None):
        logging.debug("ProxmoxManage: runVMInfo(): instantiated")
        print("Refreshing VM: " + vmName)
        try:
            try:
                nodename = self.cf.getConfig()['PROXMOX']['VMANAGE_NODE_NAME']
                proxapi = self.getProxAPI(username, password)
                if proxapi == None:
                    return None           
            except Exception:
                logging.error("Error in runVMInfo(): An error occured when trying to connect to proxmox")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
                return None

            self.readStatus = VMManage.MANAGER_READING
            
            try:
                ##TODO: instead, noly get the specific node data
                allinfo = proxapi.cluster.resources.get(type='vm')
            except Exception:
                logging.error("Error in runVMInfo(): An error occured when trying to get cluster info")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
                return -1
            vm = None
            #NEED: name, vmid, template, status
            for vmiter in allinfo:
                if 'node' not in vmiter or vmiter['node'] != nodename:
                    continue
                if vmid == None and ('name' not in vmiter or vmiter['name'] != vmName):
                    continue
                if vmid != None and ('vmid' not in vmiter or str(vmiter['vmid']) != vmid):
                    continue
                # net info
                #GET UUID
                vm = VM()
                vm.name = vmName
                if vmid == None:
                    vm.UUID = vmiter['vmid']
                else:
                    vm.UUID = vmid
                if 'template' in vmiter:
                    vm.template = vmiter['template']
                else: 
                    vm.template = 0

                try:
                    netinfo = proxapi.nodes(nodename)('qemu')(vm.UUID)('config').get()
                except Exception:
                    logging.error("Error in runVMInfo(): An error occured when trying to get vm info")
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
            if vm is None:
                logging.error("runVMInfo(): VM not found: " + vmName + "cluster info: " + str(allinfo))
                return -1

            self.vms[vm.name] = vm
            logging.debug("runVMSInfo(): completed")
        except Exception:
            logging.error("Error in runVMSInfo(): An error occured ")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
        finally:
            self.readStatus = VMManage.MANAGER_IDLE
            self.writeStatus -= 1
            logging.debug("runVMSInfo(): sub 1 "+ str(self.writeStatus))

    def runConfigureVMNet(self, vmName, netNum, netName, username=None, password=None, refreshNetwork=False):
        try:
            logging.debug("runConfigureVMNet(): instantiated")
            self.readStatus = VMManage.MANAGER_READING
            cloneNetNum = 1
            logging.debug("runConfigureVMNet(): Processing internal net names: " + str(netName))
            vmUUID = ""
            vmUUID = str(self.vms[vmName].UUID)
            createdNets = []
            try:
                nodename = self.cf.getConfig()['PROXMOX']['VMANAGE_NODE_NAME']
                proxapi = self.getProxAPI(username, password)
                if proxapi == None:
                    return None
            except Exception:
                logging.error("Error in runConfigureVMNet(): An error occured when trying to connect to proxmox")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
                return None

            try:
                ifaces_ds = proxapi.nodes(nodename)('network').get(type='bridge')
                ifaces = []
                for iface in ifaces_ds:
                    ifaces.append(iface['iface'])
            except Exception:
                logging.error("Error in runConfigureVMNet(): An error occured when trying to get bridges")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)

            try:
                #create bridge if it doesn't exist
                if netName not in ifaces and netName not in createdNets:
                    res = proxapi.nodes(nodename)('network').post(iface=str(netName),node=nodename,type='bridge',autostart=1)
                    if res == None:
                        createdNets.append(netName)
            except ResourceException:
                logging.warning("In runConfigureVMNet(): Interface may already exist: " + str(netName))
                # exc_type, exc_value, exc_traceback = sys.exc_info()
                # traceback.print_exception(exc_type, exc_value, exc_traceback)

            #assign net to bridge
            kwargs = {f'net{netNum}': 'e1000,bridge='+str(netName)}
            try:
                logging.info("runConfigureVMNet(): Configuring Interface for VMID: " + str(vmUUID))
                res = proxapi.nodes(nodename)('qemu')(vmUUID)('config').post(**kwargs)
                self.basic_blocking_task_status(proxapi, res, 'config')
            except Exception:
                logging.error("Error in runConfigureVMNet(): An error occured when trying to configure vm network device")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
            logging.info("Command Output: "+ str(res))
            cloneNetNum += 1
            if refreshNetwork:
                self.refreshNetwork()
            logging.debug("runConfigureVMNet(): Thread completed")
        except Exception:
            logging.error("runConfigureVMNet() Error")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
        finally:
            self.readStatus = VMManage.MANAGER_IDLE
            self.writeStatus -= 1
            logging.debug("runConfigureVMNet(): sub 1 "+ str(self.writeStatus))


    def runRemoteCmds(self, cmds, username=None, password=None):
        logging.debug("ProxmoxManage: runRemoteCmds(): instantiated")
        try:
            self.readStatus = VMManage.MANAGER_READING

            try:
                if username != None and len(username) > 4 and password != None and username.strip() != "" and password.strip() != "":
                    sshuser = username[:-4]
                    proxssh = self.getProxSSH(username=sshuser,password=password)
                else:
                    proxssh = self.getProxSSH(username, password)
                if proxssh == None:
                    return None
            except Exception:
                logging.error("Error in runRemoteCmds(): An error occured when trying to connect to proxmox")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
                return None
            cmdNum = 1
            for cmd in cmds:
                logging.info("runRemoteCmds(): Running cmd # " + str(cmdNum) + " of " + str(len(cmds)) + ": " + str(cmd))
                # res = proxssh._exec(shlex.split(cmd))
                res = self.executeSSH(cmd)
                logging.info("runRemoteCmds(): Command completed: " + str(res))
            logging.debug("runRemoteCmds(): Thread completed")
        except Exception:
            logging.error("runRemoteCmds() Error: " + " cmd: " + str(cmd))
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
        finally:
            self.readStatus = VMManage.MANAGER_IDLE
            self.writeStatus-=1
            logging.debug("runRemoteCmds(): sub 1 "+ str(self.writeStatus))

    def refreshNetwork(self, username=None, password=None):
        logging.debug("ProxmoxManage: refreshNetwork(): instantiated ")
        try:
            nodename = self.cf.getConfig()['PROXMOX']['VMANAGE_NODE_NAME']
            proxapi = self.getProxAPI(username, password)
            if proxapi == None:
                return None
        except Exception:
            logging.error("Error in refreshNetwork(): An error occured when trying to connect to proxmox")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
            return None

        try:
            res = proxapi.nodes(nodename)('network').put()
            # self.basic_blocking_task_status(proxapi, res, 'put')
            logging.debug("refreshNetwork(): Thread completed")
        except Exception:
            logging.error("refreshNetwork() Error")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)

    def getVMStatus(self, vmName):
        logging.debug("ProxmoxManage: getVMStatus(): instantiated " + vmName)
        if self.checkVMExistsRetry(vmName, "getVMStatus") == -1:
            return -1

        resVM = self.vms[vmName]
        #Don't want to rely on python objects in case we go with 3rd party clients in the future
        return {"vmName" : resVM.name, "vmUUID" : resVM.UUID, "setupStatus" : resVM.setupStatus, "vmState" : resVM.state, "adaptorInfo" : resVM.adaptorInfo, "groups" : resVM.groups, "latestSnapUUID": resVM.latestSnapUUID}
        
    def getManagerStatus(self):
        logging.debug("ProxmoxManage: getManagerStatus(): instantiated")
        vmStatus = {}

        for vmName in self.vms:
            resVM = self.vms[vmName]
            vmStatus[resVM.name] = {"vmUUID" : resVM.UUID, "setupStatus" : resVM.setupStatus, "vmState" : resVM.state, "adaptorInfo" : resVM.adaptorInfo, "groups" : resVM.groups}
        
        return {"readStatus" : self.readStatus, "writeStatus" : self.writeStatus, "vmstatus" : vmStatus}

    def importVM(self, filepath, username=None, password=None):
        logging.debug("ProxmoxManage: importVM(): instantiated")
        #first get the next available id using pvesh
        self.readStatus = VMManage.MANAGER_READING
        self.writeStatus += 1
        t = threading.Thread(target=self.runImportVM, args=(filepath,username, password))
        t.start()
        return 0 
    
    def runImportVM(self, filepath, username=None, password=None):
        logging.debug("ProxmoxManage: runRemoteCmds(): instantiated")
        try:
            self.readStatus = VMManage.MANAGER_READING

            try:
                pveshpath = self.cf.getConfig()['PROXMOX']['VMANAGE_PVESH_PATH']
                qmrestore = self.cf.getConfig()['PROXMOX']['VMANAGE_QMRESTORE_PATH']
                storagepath = self.cf.getConfig()['PROXMOX']['VMANAGE_STORAGE_VOL']
                proxssh = self.getProxSSH(username=username[:-4],password=password)
                if proxssh == None:
                    return None
            except Exception:
                logging.error("Error in runConfigureVMNet(): An error occured when trying to connect to proxmox")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
                return None
            try:
                #get next available id
                proposedid = random.randint(1,1000000)
                cmd = pveshpath + " get /cluster/nextid -vmid " + proposedid
                logging.info("runRemoteCmds(): Running cmd: " + str(cmd))
                # res = proxssh._exec(shlex.split(cmd))
                res = self.proxssh.ssh_client.exec_command(cmd)
                
                newid = res.strip()
                logging.info("runRemoteCmds(): Next available id: " + str(newid))
            except Exception:
                logging.error("Error in runRemoteCmds(): An error occured when trying to get next available id")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
                return None
            try:
                #import vm
                cmd = qmrestore + " " + filepath + "  " + str(newid) + " --storage " + storagepath
                logging.info("runRemoteCmds(): Running cmd: " + str(cmd))
                # res = proxssh._exec(shlex.split(cmd))
                res = self.proxssh.ssh_client.exec_command(cmd)
            except Exception:
                logging.error("Error in runRemoteCmds(): An error occured when trying to get next available id")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
                return None
            logging.debug("runRemoteCmds(): Thread completed")
        except Exception:
            logging.error("runRemoteCmds() Error: " + " cmd: " + cmd)
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
        finally:
            self.readStatus = VMManage.MANAGER_IDLE
            self.writeStatus -= 1
            logging.debug("runRemoteCmds(): sub 1 "+ str(self.writeStatus))

    def snapshotVM(self, vmName, username=None, password=None):
        logging.debug("ProxmoxManage: snapshotVM(): instantiated")
        if self.checkVMExistsRetry(vmName, "snapshotVM") == -1:
            return -1
        self.readStatus = VMManage.MANAGER_READING
        self.writeStatus += 1

        t = threading.Thread(target=self.runSnapshotVM, args=(vmName, username, password))
        t.start()

    def runSnapshotVM(self, vmName, username=None, password=None):
        logging.debug("ProxmoxManage: runSnapshotVM(): instantiated")
        try:
            vmUUID = str(self.vms[vmName].UUID)
            
            try:
                nodename = self.cf.getConfig()['PROXMOX']['VMANAGE_NODE_NAME']
                proxapi = self.getProxAPI(username, password)
                if proxapi == None:
                    return None
            except Exception:
                logging.error("Error in runConfigureVMNet(): An error occured when trying to connect to proxmox")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
                return None

            try:
                #get latest snapshot
                snapname = "s"+str(int(time.time()))
                res = proxapi.nodes(nodename)('qemu')(vmUUID)('snapshot').post(snapname=snapname, vmstate=1)
                self.basic_blocking_task_status(proxapi, res)
                logging.info("runSnapshotVM(): Snapshot created: " + snapname + " " + str(res))
            except Exception:
                logging.error("Error in runSnapshotVM(): An error occured when trying to create snapshot "+snapname+" -- perhaps it doesn't exist")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)

            logging.debug("runSnapshotVM(): Thread completed")
        except Exception:
            logging.error("runSnapshotVM() Error.")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
        finally:
            self.readStatus = VMManage.MANAGER_IDLE
            self.writeStatus -= 1
            logging.debug("snapshotVM(): sub 1 "+ str(self.writeStatus))

    def exportVM(self, vmName, filepath, username=None, password=None):
        logging.debug("ProxmoxManage: exportVM(): instantiated")
        #first remove any quotes that may have been entered before (because we will add some after we add the file and extension)
        if self.checkVMExistsRetry(vmName, "exportVM") == -1:
            return -1

        filepath = filepath.replace("\"","")
        dumpdir = os.path.join(filepath, vmName)
        #check to see if the directory exists, if not create it
        if not os.path.exists(dumpdir):
            try:
                os.makedirs(dumpdir)
            except OSError as e:
                logging.error("Error in exportVM(): An error occured when trying to create directory: " + str(e))
                return -1
        cmds = []
        #get vmid from vmName
        vmUUID = str(self.vms[vmName].UUID)
        #use vzdump to export the vm
        cmds.append("vzdump " + str(vmUUID) + " --compress zstd --mode snapshot --remove 0 --zstd 0 --notificationpolicy never --dumpdir " + filepath)

        self.readStatus = VMManage.MANAGER_READING
        self.writeStatus += 1
        t = threading.Thread(target=self.runRemoteCmds, args=(cmds,username, password))
        t.start()
        return 0

    def runExportVM(self, vmName, filepath, username=None, password=None):
        logging.debug("ProxmoxManage: runExportVM(): instantiated")
        try:
            vmUUID = str(self.vms[vmName].UUID)
            
            try:
                nodename = self.cf.getConfig()['PROXMOX']['VMANAGE_NODE_NAME']
                proxapi = self.getProxAPI(username, password)
                if proxapi == None:
                    return None
            except Exception:
                logging.error("Error in runExportVM(): An error occured when trying to connect to proxmox")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
                return None

            try:
                res = proxapi.nodes(nodename)('vzdump').post(remove='0',compress='zstd',dumpdir=filepath,vmid=vmUUID,zstd='0',notificationpolicy='never')
                self.basic_blocking_task_status(proxapi, res)
            except Exception:
                logging.error("Error in runExportVM(): An error occured when trying to export VM: " + str(vmName))
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)

            logging.debug("runExportVM(): Thread completed")
        except Exception:
            logging.error("runExportVM() Error.")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
        finally:
            self.readStatus = VMManage.MANAGER_IDLE
            self.writeStatus -= 1
            logging.debug("runExportVM(): sub 1 "+ str(self.writeStatus))

    def runStatusChangeVM(self, vmName, status, username=None, password=None, **additional_attr):
        logging.debug("ProxmoxManage: runStatusChangeVM(): instantiated")
        try:
            vmUUID = str(self.vms[vmName].UUID)
            
            try:
                nodename = self.cf.getConfig()['PROXMOX']['VMANAGE_NODE_NAME']
                proxapi = self.getProxAPI(username, password)
                if proxapi == None:
                    return None
            except Exception:
                logging.error("Error in runStatusChangeVM(): An error occured when trying to connect to proxmox")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
                return None

            try:
                if additional_attr == {}:
                    res = proxapi.nodes(nodename)('qemu')(vmUUID)('status')(status).post()
                else:
                    res = proxapi.nodes(nodename)('qemu')(vmUUID)('status')(status).post(**additional_attr)
                self.basic_blocking_task_status(proxapi, res)
            except Exception:
                logging.error("Error in runStatusChangeVM(): An error occured when trying to change vm status "+str(vmUUID)+" to " + str(status))
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)

            logging.debug("runStatusChangeVM(): Thread completed")
        except Exception:
            logging.error("runStatusChangeVM() Error.")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
        finally:
            self.readStatus = VMManage.MANAGER_IDLE
            self.writeStatus -= 1
            logging.debug("runStatusChangeVM(): sub 1 "+ str(self.writeStatus))
        
    def startVM(self, vmName, username=None, password=None):
        logging.debug("ProxmoxManage: startVM(): instantiated")
        #check to make sure the vm is known, if not should refresh or check name:
        if self.checkVMExistsRetry(vmName, "startVM") == -1:
            return -1

        self.readStatus = VMManage.MANAGER_READING
        self.writeStatus += 1
        if self.vms[vmName].state == "paused":
            t = threading.Thread(target=self.runStatusChangeVM, args=(vmName, 'resume', username, password))
        else:
            t = threading.Thread(target=self.runStatusChangeVM, args=(vmName, 'start', username, password))
        t.start()
        return 0

    def pauseVM(self, vmName, username=None, password=None):
        logging.debug("ProxmoxManage: pauseVM(): instantiated")
        if self.checkVMExistsRetry(vmName, "pauseVM") == -1:
            return -1

        self.readStatus = VMManage.MANAGER_READING
        self.writeStatus += 1
        t = threading.Thread(target=self.runStatusChangeVM, args=(vmName, 'suspend', username, password))
        t.start()
        return 0

    def suspendVM(self, vmName, username=None, password=None):
        logging.debug("ProxmoxManage: suspendVM(): instantiated")
        if self.checkVMExistsRetry(vmName, "suspendVM") == -1:
            return -1

        self.readStatus = VMManage.MANAGER_READING
        self.writeStatus += 1
        t = threading.Thread(target=self.runStatusChangeVM, args=(vmName, 'suspend', username, password), kwargs={'todisk':'1'})
        t.start()
        return 0

    def stopVM(self, vmName, username=None, password=None):
        logging.debug("ProxmoxManage: stopVM(): instantiated")
        #check to make sure the vm is known, if not should refresh or check name:
        if self.checkVMExistsRetry(vmName, "stopVM") == -1:
            return -1

        self.readStatus = VMManage.MANAGER_READING
        self.writeStatus += 1
        t = threading.Thread(target=self.runStatusChangeVM, args=(vmName, 'stop', username, password))
        t.start()
        return 0

    def removeVM(self, vmName, username=None, password=None):
        logging.debug("ProxmoxManage: removeVM(): instantiated")
        if self.checkVMExistsRetry(vmName, "removeVM",sleeptime=.05) == -1:
            return -1

        self.readStatus = VMManage.MANAGER_READING
        self.writeStatus += 1
        t = threading.Thread(target=self.runRemoveVM, args=(vmName, username, password))
        t.start()
        return 0

    def runRemoveVM(self, vmName, username=None, password=None):
        logging.debug("ProxmoxManage: runRemoveVM(): instantiated")
        try:
            self.readStatus = VMManage.MANAGER_READING
            if self.checkVMExistsRetry(vmName, "runRemoveVM",sleeptime=.05) == -1:
                return -1

            vmUUID = str(self.vms[vmName].UUID)
            
            try:
                nodename = self.cf.getConfig()['PROXMOX']['VMANAGE_NODE_NAME']
                proxapi = self.getProxAPI(username, password)
                if proxapi == None:
                    return None
            except Exception:
                logging.error("Error in runRemoveVM(): An error occured when trying to connect to proxmox")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
                return None
            success = False
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

    def removeNetworks(self, netNames, username=None, password=None):
        logging.debug("ProxmoxManage: removeNetworks(): instantiated")

        self.readStatus = VMManage.MANAGER_READING
        self.writeStatus += 1
        t = threading.Thread(target=self.runRemoveNetworks, args=(netNames, username, password))
        t.start()
        return 0

    def runRemoveNetworks(self, netNames, username=None, password=None):
        logging.debug("ProxmoxManage: runRemoveNetworks(): instantiated")
        try:
            self.readStatus = VMManage.MANAGER_READING
            
            try:
                nodename = self.cf.getConfig()['PROXMOX']['VMANAGE_NODE_NAME']
                proxapi = self.getProxAPI(username, password)
                if proxapi == None:
                    return None
            except Exception:
                logging.error("Error in runRemoveNetworks(): An error occured when trying to connect to proxmox")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
                return None
            success = False
            for netName in netNames:
                try:
                    proxapi.nodes(nodename)('network').delete(netName)
                    success = True
                except Exception:
                    print("Warning in runRemoveNetworks(): Could not delete network adaptor "+str(netName)+" -- perhaps it doesn't exist")
                    #exc_type, exc_value, exc_traceback = sys.exc_info()
                    #traceback.print_exception(exc_type, exc_value, exc_traceback)

            logging.debug("runRemoveNetworks(): Thread completed")
        except Exception:
            logging.error("runRemoveNetworks() Error.")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
        finally:
            self.readStatus = VMManage.MANAGER_IDLE
            self.writeStatus -= 1
            logging.debug("runRemoveNetworks(): sub 1 "+ str(self.writeStatus))

    def cloneVMConfigAll(self, vmName, cloneName, cloneSnapshots, linkedClones, groupName, internalNets, vrdpPort, refreshVMInfo=False, username=None, password=None):
        logging.debug("ProxmoxManage: cloneVMConfigAll(): instantiated")
        if self.checkVMExistsRetry(vmName, "cloneVMConfigAll") == -1:
            return -1

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
            #first clone
            if self.checkVMExistsRetry(vmName, "runCloneVMConfigAll_vm") == -1:
                return -1

            # clone the VM
            self.writeStatus += 1
            self.runCloneVM(vmName, cloneName, cloneSnapshots, linkedClones, groupName, username, password)
            
            #netsetup
            #Check that clone exists
            if self.checkVMExistsRetry(cloneName, "runCloneVMConfigAll_clone") == -1:
                return -1

            self.writeStatus += 1
            self.runConfigureVMNets(cloneName, internalNets, username, password)

            #vrdp setup (if applicable)
            if vrdpPort != None:
                self.writeStatus += 1
                self.runEnableVRDP(cloneName, vrdpPort, username, password)
            
            #create snap
            self.writeStatus += 1
            self.runSnapshotVM(cloneName, username, password)
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
        #Check that vm does exist
        if self.checkVMExistsRetry(vmName, "cloneVM") == -1:
            return -1

        if refreshVMInfo == True:
            self.readStatus = VMManage.MANAGER_READING
            self.writeStatus += 1
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
            #First check that the clone doesn't exist:
            exists = cloneName in self.vms
            if exists:
                logging.warning("runCloneVM(): A VM with the clone name already exists and is registered... skipping " + str(cloneName))
                return

            vmUUID = str(self.vms[vmName].UUID)
            
            try:
                nodename = self.cf.getConfig()['PROXMOX']['VMANAGE_NODE_NAME']
                proxapi = self.getProxAPI(username, password)
                if proxapi == None:
                    return None
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
                    self.basic_blocking_task_status(proxapi, res)
                    self.vms[vmName].template = 1
                    logging.info("runCloneVM(): Completed setting vm to template: " + str(res))
                except Exception:
                    print("Error in <>(): An error occured when trying set vm to template")
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    traceback.print_exception(exc_type, exc_value, exc_traceback)
                    exit -1

            #get next free vmid
            try:
                proposedid = random.randint(1,1000000)
                newid = proxapi.cluster('nextid').get(vmid=proposedid)
                logging.info("runCloneVM(): Retrieved next available vm id: " + str(newid))
            except ResourceException:
                print("Random-generated id already exists... asking proxmox for nextid instead")
                newid = proxapi.cluster('nextid').get()
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)

            except Exception:
                print("Error in runCloneVM(): An error occured when trying to get a new vm id")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
                exit -1

            #now issue the create clone command
            try:
                res = proxapi.nodes(nodename)('qemu')(vmUUID)('clone').post(name=cloneName, newid=newid, full=0)
                self.basic_blocking_task_status(proxapi, res)
                logging.info("runCloneVM(): Clone created: " + str(res))
            except Exception:
                print("Error in runCloneVM(): An error occured when trying to set clone vm")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback)
            # once it's a template, I don't think there's a way back... so we'll just leave it as a template for now
            # try:
            #     res = proxapi.nodes(nodename)('qemu')(vmUUID)('config').post(template=0)
            #     self.basic_blocking_task_status(proxapi, res)
            #     logging.info("runCloneVM(): Completed setting vm to non-template mode: " + str(res))
            # except Exception:
            #     print("Error in runCloneVM An error occured when trying to set vm to non-template mode")
            #     exc_type, exc_value, exc_traceback = sys.exc_info()
            #     traceback.print_exception(exc_type, exc_value, exc_traceback)
            self.writeStatus += 1
            #just add to self.vms if it's not there and then call the vminfo
            self.runVMInfo(cloneName, username, password, newid)

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
        if self.checkVMExistsRetry(vmName, "enableVRDPVM") == -1:
            return -1

        self.readStatus = VMManage.MANAGER_READING
        self.writeStatus += 1
        t = threading.Thread(target=self.runEnableVRDP, args=(vmName, vrdpPort, username, password))
        t.start()
        return 0

    def runEnableVRDP(self, vmName, vrdpPort, username=None, password=None):
        logging.debug("ProxmoxManage: runEnableVRDP(): instantiated")
        if self.checkVMExistsRetry(vmName, "runEnableVRDP") == -1:
            return -1

        self.readStatus = VMManage.MANAGER_READING

        logging.debug("runEnableVRDP(): Processing restore latest snapshot for: " + str(vmName))
        vmUUID = ""
        vmUUID = str(self.vms[vmName].UUID)

        try:
            #add vnc port to config file            
            vncport = int(vrdpPort) - 5900
            cmds = []
            # cmds.append('sed -i "/vnc/d" /etc/pve/qemu-server/' + str(vmUUID) + '.conf')
            # cmds.append('sed -i "1 a args: -vnc 0.0.0.0:'+str(vncport)+'" /etc/pve/qemu-server/' + str(vmUUID) + '.conf')
            self.readStatus = VMManage.MANAGER_READING
            self.writeStatus += 1
            self.runRemoteCmds(cmds,username, password)
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

            logging.debug("runRestoreLatestSnapVM(): Processing restore latest snapshot for: " + str(vmName))
            vmUUID = ""
            vmUUID = str(self.vms[vmName].UUID)
            try:
                nodename = self.cf.getConfig()['PROXMOX']['VMANAGE_NODE_NAME']
                proxapi = self.getProxAPI(username, password)
                if proxapi == None:
                    return None
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
                    self.basic_blocking_task_status(proxapi, res)
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
        if self.checkVMExistsRetry(vmName, "restoreLatestSnapVM") == -1:
            return -1

        cmd = "snapshot " + str(self.vms[vmName].UUID) + " restorecurrent"
        self.readStatus = VMManage.MANAGER_READING
        self.writeStatus += 1
        t = threading.Thread(target=self.runRestoreLatestSnapVM, args=(vmName,username,password))
        t.start()
        return 0