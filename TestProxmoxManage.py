from subprocess import Popen, PIPE
import subprocess
import sys
from sys import argv, platform
import traceback
import logging
import shlex
import threading
import time
from engine.Manager.VMManage.VMManage import VMManage
from engine.Manager.VMManage.VM import VM
import os
import re
import configparser
from engine.Configuration.SystemConfigIO import SystemConfigIO
from engine.Manager.VMManage.ProxmoxManage import ProxmoxManage
        
if __name__ == "__main__":
    logging.getLogger().setLevel(logging.DEBUG)
    logging.info("Starting Program")
    logging.info("Instantiating VMwareManageWin")
    s = SystemConfigIO()
    vmpath = s.getConfig()["VMWARE"]["VMANAGE_VM_PATH"]
    
    vbm = ProxmoxManage()
    
    logging.info("Status without refresh: ")
    vbm.getManagerStatus()
    
    logging.info("Refreshing VM Info")
    for vm in vbm.vms:
        logging.info("VM Info:\r\n" + str(vm))
    vbm.refreshAllVMInfo(username, password)
    result = vbm.getManagerStatus()["writeStatus"]
    while result != vbm.MANAGER_IDLE:
    #waiting for manager to finish query...
        result = vbm.getManagerStatus()["writeStatus"]
        time.sleep(.1)
    logging.info("Refreshing VMs Info - AFTER")

    #get vm info from objects
    for vm in vbm.vms:
        logging.info("VM Info:\r\nName: " + str(vbm.vms[vm].name) + "\r\nState: " + str(vbm.vms[vm].state) + "\r\n" + "Groups: " + str(vbm.vms[vm].groups) + "\r\n" + "latestSnap: " + str(vbm.vms[vm].latestSnapUUID) + "\r\n")
        for adaptor in vbm.vms[vm].adaptorInfo:
            logging.info("adaptor: " + str(adaptor) + " Type: " + str(vbm.vms[vm].adaptorInfo[adaptor]) + "\r\n")
    
    logging.info("Refreshing single VM Info--")
    logging.info("Result: " + str(vbm.refreshVMInfo(testvmname,username, password)))

    while vbm.getManagerStatus()["writeStatus"] != VMManage.MANAGER_IDLE:
        logging.info("waiting for manager to finish query...")
        time.sleep(.1)
    
    logging.info("Status for " + testvmname)
    logging.info(vbm.getVMStatus(testvmname,username, password))

    logging.info("Testing clone -- creating 1 clone of " + str(testvmname))
    groupName = "sampleGroup"
    tmpCloneName = testvmname+"1"
    
    vbm.cloneVM(testvmname, cloneName=str(tmpCloneName), cloneSnapshots="true", linkedClones="true", groupName=groupName, username=username, password=password)
    while vbm.getManagerStatus()["writeStatus"] != VMManage.MANAGER_IDLE:
        logging.info("testing clone waiting for manager to finish query..." + str(vbm.getManagerStatus()["writeStatus"]))
        time.sleep(.1)
    
    logging.info("Refreshing after clone since we added a new VM")
    vbm.refreshAllVMInfo(username=username, password=password)
    result = vbm.getManagerStatus()["writeStatus"]
    while result != vbm.MANAGER_IDLE:
    #waiting for manager to finish query...
        result = vbm.getManagerStatus()["writeStatus"]
        time.sleep(.1)
    logging.info("Refreshing VMs Info - AFTER")

    #get vm info from objects
    for vm in vbm.vms:
        logging.info("VM Info:\r\nName: " + str(vbm.vms[vm].name) + "\r\nState: " + str(vbm.vms[vm].state) + "\r\n" + "Groups: " + str(vbm.vms[vm].groups) + "\r\n" + "latestSnap: " + str(vbm.vms[vm].latestSnapUUID) + "\r\n")
        for adaptor in vbm.vms[vm].adaptorInfo:
            logging.info("adaptor: " + str(adaptor) + " Type: " + str(vbm.vms[vm].adaptorInfo[adaptor]) + "\r\n")

    logging.info("Testing set interface 1 on clone -- " + tmpCloneName)
    vbm.configureVMNet(vmName=tmpCloneName, netNum="0", netName="intnet1", username=username, password=password)
    while vbm.getManagerStatus()["writeStatus"] != VMManage.MANAGER_IDLE:
        logging.info("waiting for manager to finish query...")
        time.sleep(.1)

    logging.info("Testing enable VRDP on clone -- " + tmpCloneName + " port 5901")
    vbm.enableVRDPVM(tmpCloneName, "5901", username=username[:-4], password=password)
    while vbm.getManagerStatus()["writeStatus"] != VMManage.MANAGER_IDLE:
        logging.info("waiting for manager to finish query...")
        time.sleep(.1)

    logging.info("Testing snapshot after clone -- " + tmpCloneName)
    vbm.snapshotVM(tmpCloneName, username=username, password=password)
    while vbm.getManagerStatus()["writeStatus"] != VMManage.MANAGER_IDLE:
        logging.info("waiting for manager to finish query...")
        time.sleep(.1)

    logging.info("----Testing VM commands-------")
    logging.info("----Start-------")
    vbm.startVM(tmpCloneName, username=username, password=password)
    while vbm.getManagerStatus()["writeStatus"] != VMManage.MANAGER_IDLE:
        logging.info("waiting for manager to finish reading/writing...")
        time.sleep(.1)
    logging.info("----Waiting 5 seconds to pause -------")
    time.sleep(5)

    vbm.pauseVM(tmpCloneName, username=username, password=password)
    while vbm.getManagerStatus()["writeStatus"] != VMManage.MANAGER_IDLE:
        logging.info("waiting for manager to finish reading/writing...")
        time.sleep(.1)
    logging.info("----Waiting 5 seconds to resume -------")
    time.sleep(5)

    vbm.snapshotVM(tmpCloneName, username=username, password=password)
    while vbm.getManagerStatus()["writeStatus"] != VMManage.MANAGER_IDLE:
        logging.info("waiting for manager to finish reading/writing...")
        time.sleep(.1)
    logging.info("----Waiting 5 seconds to snapshot -------")
    time.sleep(5)

    vbm.startVM(tmpCloneName, username=username, password=password)
    while vbm.getManagerStatus()["writeStatus"] != VMManage.MANAGER_IDLE:
        logging.info("waiting for manager to finish reading/writing...")
        time.sleep(.1)
    logging.info("----Waiting 5 seconds to stop-------")
    time.sleep(5)

    vbm.suspendVM(tmpCloneName, username=username, password=password)
    while vbm.getManagerStatus()["writeStatus"] != VMManage.MANAGER_IDLE:
        logging.info("waiting for manager to finish reading/writing...")
        time.sleep(.1)
    logging.info("----Waiting 5 seconds to resume -------")
    time.sleep(5)
    
    vbm.startVM(tmpCloneName, username=username, password=password)
    while vbm.getManagerStatus()["writeStatus"] != VMManage.MANAGER_IDLE:
        logging.info("waiting for manager to finish reading/writing...")
        time.sleep(.1)
    logging.info("----Waiting 5 seconds to stop-------")
    time.sleep(5)
# ##Test guestCommands -- only works when VMware Tools is installed
#     cmds = []
#     cmds.append("-gu user -gp pass CopyFileFromHostToGuest \"" + testvmname + "\" utils/checkConns.sh /tmp/checkConns.sh")
#     cmds.append("-gu user -gp pass runProgramInGuest \"" + testvmname + "\" /tmp/checkConns.sh")
#     cmds.append("-gu user -gp pass CopyFileFromGuestToHost \"" + testvmname + "\" /tmp/output.txt output1.txt")
#     cmds.append("-gu user -gp pass deleteFileInGuest \"" + testvmname + "\" /tmp/output.txt")
#     cmds.append("-gu user -gp pass deleteFileInGuest \"" + testvmname + "\" /tmp/checkConns.sh")
#     cmds.append("-gu user -gp pass runProgramInGuest \"" + testvmname + "\" -interactive /usr/bin/notify-send \"From Acosta\" \"Try again\" -u critical -A OK -a Acosta")
    
#     guestCmds = cmds

    # vbm.guestCommands(tmpCloneName, guestCmds)
    # while vbm.getManagerStatus()["writeStatus"] != VMManage.MANAGER_IDLE and vbm.getManagerStatus()["writeStatus"] != VMManage.MANAGER_IDLE:
    #     logging.info("waiting for manager to finish reading/writing...")
    #     time.sleep(.1)
    # logging.info("----Waiting 15 seconds to stop-------")
    # time.sleep(15)

    vbm.stopVM(tmpCloneName, username=username, password=password)
    while vbm.getManagerStatus()["writeStatus"] != VMManage.MANAGER_IDLE and vbm.getManagerStatus()["writeStatus"] != VMManage.MANAGER_IDLE:
        logging.info("waiting for manager to finish reading/writing...")
        time.sleep(.1)
    time.sleep(5)
    logging.info("Testing remove -- removing 1 clone of " + str(testvmname))
    
    vbm.removeVM(tmpCloneName, username=username, password=password)
    while vbm.getManagerStatus()["writeStatus"] != VMManage.MANAGER_IDLE:
        logging.info("testing clone waiting for manager to finish query..." + str(vbm.getManagerStatus()["writeStatus"]))
        time.sleep(.1)


    time.sleep(10)
    logging.info("Final Manager Status: " + str(vbm.getManagerStatus()))

    logging.info("Completed Exiting...")
