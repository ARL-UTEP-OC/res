from proxmoxer import ProxmoxAPI
from proxmoxer.core import ResourceException
from proxmoxer.backends import ssh_paramiko

import time
import traceback
import sys
import shlex

nodename='acostave'
proxapi = ProxmoxAPI('server', port=port, user='user@pam', password='pass', verify_ssl=False)
proxssh = ssh_paramiko.SshParamikoSession('server',port=port, user='user',password='pass')
#######Get vm power status:
vmstatuss = {}
allinfo = proxapi.cluster.resources.get(type='vm')

for vmiter in allinfo:
    # net info
    tmpvmid = vmiter['vmid']
    try:
        netinfo = proxapi.nodes('acostave')('qemu')(tmpvmid)('config').get()
    except Exception:
        #logging.error("Error in <>(): An error occured ")
        print("Error in <>(): An error occured when trying to get node config")
        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback.print_exception(exc_type, exc_value, exc_traceback)

    # num interfaces
    nics = [value for key, value in netinfo.items() if 'net' in key.lower()]
    adaptorInfo = {}
    for nic in nics:
        type=nic.split(',')[1].split("=")[0]
        name=nic.split(',')[1].split("=")[1]
        adaptorInfo[name] = type
    if 'template' in vmiter:
        vmstatuss[vmiter['name']] = {'id': str(vmiter['vmid']), 'status': vmiter['status'], 'adaptorInfo': adaptorInfo, 'template': vmiter['template']} 
    else: 
        vmstatuss[vmiter['name']] = {'id': str(vmiter['vmid']), 'status': vmiter['status'], 'adaptorInfo': adaptorInfo, 'template': 0} 

print("STATUS:\n" + str(vmstatuss))

#######Create clone
#get all vm infos:
#cluster/resources?type=vm
try:
    allinfo = proxapi.cluster.resources.get(type='vm')
except Exception:
    #logging.error("Error in <>(): An error occured ")
    print("Error in <>(): An error occured when trying to get vm info")
    exc_type, exc_value, exc_traceback = sys.exc_info()
    traceback.print_exception(exc_type, exc_value, exc_traceback)

#get id from name
vmid = vmstatuss['NetworkMachine']['id']
#check if vm is a template already, if not, make it one
istemplate = vmstatuss['NetworkMachine']['template']
#convert to template (to allow linked clones)
if istemplate == False:
    try:
        res = proxapi.nodes('acostave')('qemu')(vmid)('template').post(node='acostave', vmid=vmid)
    except Exception:
        #logging.error("Error in <>(): An error occured ")
        print("Error in <>(): An error occured when trying set vm to template")
        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback.print_exception(exc_type, exc_value, exc_traceback)
        exit -1

#get next free vmid
try:
    newid = proxapi.cluster('nextid').get()
except Exception:
    #logging.error("Error in <>(): An error occured ")
    print("Error in <>(): An error occured when trying to get a new vm id")
    exc_type, exc_value, exc_traceback = sys.exc_info()
    traceback.print_exception(exc_type, exc_value, exc_traceback)
    exit -1

#now issue the create clone command
try:
    status = proxapi.nodes('acostave')('qemu')(vmid)('clone').post(newid=newid,node='acostave',vmid=vmid, full=0)
except Exception:
    #logging.error("Error in <>(): An error occured ")
    print("Error in <>(): An error occured when trying to set clone vm")
    exc_type, exc_value, exc_traceback = sys.exc_info()
    traceback.print_exception(exc_type, exc_value, exc_traceback)
try:
    res = proxapi.nodes('acostave')('qemu')(vmid)('config').post(node='acostave', vmid=vmid, template=0)
except Exception:
    #logging.error("Error in <>(): An error occured ")
    print("Error in <>(): An error occured when trying to set vm to non-template mode")
    exc_type, exc_value, exc_traceback = sys.exc_info()
    traceback.print_exception(exc_type, exc_value, exc_traceback)

#######Change netname (bridge)
#create bridge if it doesn't exist
bridges = []
try:
    ifaces = proxapi.nodes('acostave')('network').get(type='bridge')
except Exception:
    #logging.error("Error in <>(): An error occured ")
    print("Error in <>(): An error occured when trying to get bridges")
    exc_type, exc_value, exc_traceback = sys.exc_info()
    traceback.print_exception(exc_type, exc_value, exc_traceback)
exists = False

nicnum = 0
for nicnum in range(len(nics)):
    try:
        proxapi.nodes('acostave')('network').post(iface='testnet'+str(nicnum),node='acostave',type='bridge')
    except ResourceException:
        #logging.error("Error in <>(): An error occured ")
        print("Error in <>(): An error occured; interface may already exist: " + "testnet1")
        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback.print_exception(exc_type, exc_value, exc_traceback)
        continue

#assign nets to bridges
nicnum = 0
for nicnum in range(len(nics)):
    kwargs = {f'net{nicnum}': 'e1000,bridge=testnet'+str(nicnum)}
    try:
        proxapi.nodes('acostave')('qemu')(newid)('config').post(**kwargs)
    except Exception:
        #logging.error("Error in <>(): An error occured ")
        print("Error in <>(): An error occured when trying to configure vm network device")
        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback.print_exception(exc_type, exc_value, exc_traceback)

#enable vnc
#proxapi.nodes('acostave')('network').post(iface='testnet'+str(nicnum),node='acostave',type='bridge')
vncport = 1
cmd = 'sed -i "$ a args: -vnc 0.0.0.0:'+str(vncport)+'" /etc/pve/qemu-server/' + str(newid) + '.conf'
try:
    proxssh._exec(shlex.split(cmd))
except Exception:
    #logging.error("Error in <>(): An error occured ")
    print("Error in <>(): An error occured when trying to set vnc port")
    exc_type, exc_value, exc_traceback = sys.exc_info()
    traceback.print_exception(exc_type, exc_value, exc_traceback)

########Start clone
try:
    proxapi.nodes('acostave')('qemu')(newid)('status')('start').post()
except Exception:
    #logging.error("Error in <>(): An error occured ")
    print("Error in <>(): An error occured when trying to start vm "+str(id)+" -- perhaps it doesn't exist")
    exc_type, exc_value, exc_traceback = sys.exc_info()
    traceback.print_exception(exc_type, exc_value, exc_traceback)

########Stop clone
try:
    proxapi.nodes('acostave')('qemu')(newid)('status')('stop').post()
except Exception:
    #logging.error("Error in <>(): An error occured ")
    print("Error in <>(): An error occured when trying to stop vm "+str(id)+" -- perhaps it doesn't exist")
    exc_type, exc_value, exc_traceback = sys.exc_info()
    traceback.print_exception(exc_type, exc_value, exc_traceback)

########Suspend clone
try:
    proxapi.nodes('acostave')('qemu')(newid)('status')('suspend').post()
except Exception:
    #logging.error("Error in <>(): An error occured ")
    print("Error in <>(): An error occured when trying to suspend vm "+str(id)+" -- perhaps it doesn't exist")
    exc_type, exc_value, exc_traceback = sys.exc_info()
    traceback.print_exception(exc_type, exc_value, exc_traceback)

########Resume clone
try:
    proxapi.nodes('acostave')('qemu')(newid)('status')('resume').post()
except Exception:
    #logging.error("Error in <>(): An error occured ")
    print("Error in <>(): An error occured when trying to resume vm "+str(id)+" -- perhaps it doesn't exist")
    exc_type, exc_value, exc_traceback = sys.exc_info()
    traceback.print_exception(exc_type, exc_value, exc_traceback)

########Snapshot clone
try:
    #get latest snapshot
    snapname = "s"+str(int(time.time()))
    snaps = proxapi.nodes('acostave')('qemu')(newid)('snapshot').post(snapname=snapname)
        
except Exception:
    #logging.error("Error in <>(): An error occured ")
    print("Error in <>(): An error occured when trying to create snapshot "+snapname+" -- perhaps it doesn't exist")
    exc_type, exc_value, exc_traceback = sys.exc_info()
    traceback.print_exception(exc_type, exc_value, exc_traceback)

########Revert to Snapshot clone
try:
    #get latest snapshot
    latest_snap = None
    snaps = proxapi.nodes('acostave')('qemu')(newid)('snapshot').get()
    for snap in snaps:
        if 'parent' in snap and snap['name'] == 'current':
            latest_snap = snap['parent']

    #restore latest snapshot
    if latest_snap != None:
        proxapi.nodes('acostave')('qemu')(newid)('snapshot')(latest_snap)('rollback').post(start='0')
    else:
        Exception
        
except Exception:
    #logging.error("Error in <>(): An error occured ")
    print("Error in <>(): An error occured when trying to delete vm "+str(id)+" -- perhaps it doesn't exist")
    exc_type, exc_value, exc_traceback = sys.exc_info()
    traceback.print_exception(exc_type, exc_value, exc_traceback)

########Delete clone
try:
    proxapi.nodes('acostave')('qemu')(newid).delete(node='acostave', vmid=newid)
except Exception:
    #logging.error("Error in <>(): An error occured ")
    print("Error in <>(): An error occured when trying to delete vm "+str(id)+" -- perhaps it doesn't exist")
    exc_type, exc_value, exc_traceback = sys.exc_info()
    traceback.print_exception(exc_type, exc_value, exc_traceback)

#delete bridge
try:
     proxapi.nodes('acostave')('network')('testnet1').delete(node='acostave')
except ResourceException:
    #logging.error("Error in <>(): An error occured ")
    print("Error in <>(): An error occured; interface may not exist: " + "testnet1")
    exc_type, exc_value, exc_traceback = sys.exc_info()
    traceback.print_exception(exc_type, exc_value, exc_traceback)
