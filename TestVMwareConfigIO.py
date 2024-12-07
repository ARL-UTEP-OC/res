from engine.Configuration.VMwareConfigIO import VMwareConfigIO
from engine.Configuration.SystemConfigIO import SystemConfigIO
import re
import os

# Example usage
s = SystemConfigIO()
vc = VMwareConfigIO()

# helper function to perform sort
def num_sort(test_string):
    return list(map(int, re.findall(r'\d+', test_string)))[0]

filename = s.getConfig()['VMWARE']['VMWARE_INVENTORYFILE_PATH']
# filename = s.getConfig()['VMWARE']['VMWARE_INVENTORYFILE_PATH'][:-4]
# filename = filename + str("mine")
                          
my_list = vc.refresh_inventory_to_dict(filename)
print(my_list)

print("ID LIST: ")
idlist = vc.get_matching_keys(my_list, 'index*')
realvmlist = vc.get_keys_with_config(my_list, idlist, "id")
print(realvmlist)

vm_nics = {}
realvmlist = vc.get_vmlist_name()
for vm in realvmlist:
    vm_nics[vm] = vc.get_vmnics(vm)
print(vm_nics)

vmlist = vc.get_vmlist_name()
print(vmlist)

vmgroup = vc.get_vmgroups_name()
print(vmgroup)

#cloning testing
###get vmlists
vmlists = vc.get_matching_keys(my_list, "vmlist*")

#get list of VMs and groups
vms_vmlist = vc.get_keys_with_config(my_list, vmlists, "IsClone")
groups_vmlist = vc.get_keys_with_config(my_list, vmlists, "Expanded")

vms_names = {}
groups_names = {}
for vm in vms_vmlist:
    display_name = my_list[vm]["config"]
    vms_names[display_name] = vm

for group in groups_vmlist:
    display_name = my_list[group]["config"]
    groups_names[display_name] = group

tmpVMName = "C:\\Users\\Acosta\\VMWare_VMs\\testVMTemplate\\defaulta.vmx"
tmpVMName_vmlist = vms_names[tmpVMName]
tmpCloneName = "C:\\Users\\Acosta\\VMWare_VMs\\testVMTemplate1\\defaulta1.vmx"
tmpGroupName = "GeneratedGroup"

# 1. look at all vms
#  if the vm is already there, print error and return
#  otherwise, get highest ItemID (vmlist#)
if tmpCloneName in vms_names:
    print("Already exists")
    exit(-1)

###GROUP ID/CREATION###
#Get the vmlist# associated with the existing group
vmlists.sort(key=num_sort)
current_high = re.findall(r'\d+', vmlists[-1])[0]

if tmpGroupName in groups_names:
    group_vmlist = groups_names[tmpGroupName]
    parent_id =  re.findall(r'\d+', group_vmlist[-1])[0]
else:
    #otherwise create the group
    vmlists.sort(key=num_sort)
    current_high = re.findall(r'\d+', vmlists[-1])[0]
    current_high = str(int(current_high)+1)
    new_groupentry_header = "vmlist"+(current_high)
    my_list[new_groupentry_header] = {}
    my_list[new_groupentry_header]['config'] = 'folder'+str(current_high)
    my_list[new_groupentry_header]['Type'] = '2'
    my_list[new_groupentry_header]['DisplayName'] = tmpGroupName
    my_list[new_groupentry_header]['ParentID'] = tmpGroupName
    my_list[new_groupentry_header]['ItemID'] = str(current_high)
    #my_list[new_groupentry_header]['SeqID'] = '0'
    my_list[new_groupentry_header]['IsFavorite'] = 'FALSE'
    #my_list[new_groupentry_header]['UUID'] = tmpGroupName
    my_list[new_groupentry_header]['Expanded'] = 'TRUE'
    parent_id = current_high

    # vmlist1.config = "folder1"
    # vmlist1.Type = "2"
    # vmlist1.DisplayName = "group1"
    # vmlist1.ParentID = "0"
    # vmlist1.ItemID = "1"
    # vmlist1.SeqID = "0"
    # vmlist1.IsFavorite = "FALSE"
    # vmlist1.UUID = "folder:52 f7 8f df c3 16 b9 ed-3e fd 26 8d fd 44 84 5f"
    # vmlist1.Expanded = "FALSE"


###VM CLONE CREATION
vmlists.sort(key=num_sort)
current_high = str(int(current_high)+1)
new_vmentry_header = "vmlist"+(current_high)

my_list[new_vmentry_header] = my_list[tmpVMName_vmlist].copy()

#num = 1
my_list[new_vmentry_header]['config'] = tmpCloneName
my_list[new_vmentry_header]['DisplayName'] = os.path.basename(tmpCloneName)[:-4]
my_list[new_vmentry_header]['ItemID'] = current_high
my_list[new_vmentry_header]['ParentID'] = parent_id
#my_list[new_vmentry_header]['SeqID'] = num
#num+=1
my_list[new_vmentry_header]['IsClone'] = "TRUE"

oresult = [""]
vc.dict_to_dot(my_list, oresult)
print("RESULT:\n" + oresult[0])

vc.write_dict2dot_file(my_list)

#  if groupname specified, then 
#   if it doesn't exist
#    add new entry for folder name
#   else (does exist)
#    get ItemID of folder name

# sample entry:
# vmlist1.config = "folder1"
# vmlist1.Type = "2"
# vmlist1.DisplayName = "group1"
# vmlist1.ParentID = "0"
# vmlist1.ItemID = "1"
# vmlist1.SeqID = "0"
# vmlist1.IsFavorite = "FALSE"
# vmlist1.UUID = "folder:52 f7 8f df c3 16 b9 ed-3e fd 26 8d fd 44 84 5f"
# vmlist1.Expanded = "FALSE"

#  add entry for the VM with ItemID of folder name (should base off of original)
# sample entry:

# vmlist2.config = "C:\Users\Acosta\VMWare_VMs\kali-linux-2024.3-vmware-amd64.vmwarevm\kali-linux-2024.3-vmware-amd64.vmx"
# vmlist2.DisplayName = "kali-linux-2024.3-vmware-amd64"
# vmlist2.ParentID = "4"
# vmlist2.ItemID = "2"
# vmlist2.SeqID = "0"
# vmlist2.IsFavorite = "FALSE"
# vmlist2.IsClone = "FALSE"
# vmlist2.CfgVersion = "8"
# vmlist2.State = "normal"
# vmlist2.UUID = "56 4d 80 f4 a7 68 30 11-89 e7 1a d8 85 f2 dd 80"
# vmlist2.IsCfgPathNormalized = "TRUE"
# vmlist14.config = "C:\Users\Acosta\OneDrive - The University of Texas at El Paso\Documents\Virtual Machines\defaulta1\defaulta1.vmx"
# vmlist14.DisplayName = "defaulta1"
# vmlist14.ParentID = "0"
# vmlist14.ItemID = "14"
# vmlist14.SeqID = "4"
# vmlist14.IsFavorite = "FALSE"
# vmlist14.IsClone = "TRUE"
# vmlist14.CfgVersion = "8"
# vmlist14.State = "normal"
# vmlist14.UUID = ""
# vmlist14.IsCfgPathNormalized = "TRUE"
