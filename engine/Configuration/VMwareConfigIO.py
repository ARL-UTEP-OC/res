from engine.Configuration.SystemConfigIO import SystemConfigIO
import sys, traceback
import logging
import re

class VMwareConfigIO():
    def __init__(self):
        logging.debug("VMwareConfigIO(): instantiated")
        self.vmgroups_dict = {}
        self.vminventory_dict = {}
        self.s = SystemConfigIO()
        self.inventory_filename = self.s.getConfig()['VMWARE']['VMWARE_INVENTORYFILE_PATH']
        self.vminventory_dict = self.refresh_inventory_to_dict(self.inventory_filename)
        self.vmgroups_dict = self.get_vmgroups_name()
    
    def get_matching_keys(self, config_dict, pattern):
        logging.debug("VMwareConfigIO(): get_matching_keys instantiated")
        matching_keys = []
        for key in config_dict:
            if re.match(pattern, key):
                matching_keys.append(key)
        return matching_keys
    
    def get_keys_with_config(self, config_dict, keys, config):
        logging.debug("VMwareConfigIO(): get_keys_with_config instantiated")
        matching_keys = []
        for akey in keys:
            if config in config_dict[akey]:
                matching_keys.append(akey)
        return matching_keys

    def dot_to_dict(self, string, value):
        """Converts a dot-separated string into a nested dictionary."""
        logging.debug("VMwareConfigIO(): dot_to_dict instantiated")
        result = {}
        keys = string.split('.')
        current = result
        for key in keys[:-1]:
            current[key] = {}
            current = current[key]
        current[keys[-1]] = value
        return result
    
    def dict_to_dot(self, pdict, out_result, parentkeys=""):
        logging.debug("VMwareConfigIO(): dict_to_dot instantiated")
        if len(out_result) != 1:
            logging.error("VMwareConfigIO: Wrong parameter type; expected string array of size 1")
            return
        for key, value in pdict.items():
            if isinstance(value, dict):
                #print(parentkeys + f'{key}:')
                self.dict_to_dot(value, out_result, parentkeys + f'{key}')
            else:
                #print(parentkeys + f'.{key} = \"{value}\"')
                if key == "":
                    out_result[0] += parentkeys + f'{key} = \"{value}\"\n'
                else:
                    out_result[0] += parentkeys + f'.{key} = \"{value}\"\n'

    def write_dict2dot_file(self, pdict, ofilename=""):
        logging.debug("write_dict2dot_file: writeConfig(): instantiated")
        try:
            if ofilename == "":
                ofilename = self.inventory_filename
            logging.debug("write_dict2dot_file(): converting dict to dot-separated")
            oresult = [""]
            self.dict_to_dot(pdict, oresult)
            with open(ofilename, 'w', encoding="utf-8") as inv_filename:
                inv_filename.write(oresult[0])
        except Exception:
            logging.error("Error in write_dict2dot_file(): An error occured ")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
            return None

    def vmx_to_dict(self, filename):
        logging.debug("VMwareConfigIO(): vmx_to_dict instantiated")
        result = {}
        invalid_lines = []
        try:
            with open(filename, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or '=' not in line:
                        logging.error("Found line without key/value: " + str(line))
                        invalid_lines.append(line)
                        continue  # Skip empty lines and lines without a separator
                    elif "." not in line:
                        logging.warning("Found line without '.': " + str(line))
                        splitline = line.split("=")
                        if len(splitline<2):
                            logging.error("Found line without value: " + str(line))
                            continue
                        left = splitline[0].strip()
                        right = splitline[1].strip()
                        if left not in result:
                            result[left] = {}
                            result[left][""] = {}
                        result[left][""] = right.strip()
                    else:
                        splitline = line.split(".")
                        name = splitline[0].strip()
                        right = '.'.join(splitline[1:]).strip()
                        if name not in result:
                            result[name] = {}

                        name2 = right.split("=")[0].strip()
                        settingval = line.split("=")[1].strip().replace("\"","")

                        result[name][name2] = settingval
            return result
        except FileNotFoundError:
            logging.error("Error in read_lines_to_dict_list(): File not found: " + str(filename))
            return None
        except Exception:
            logging.error("Error in read_lines_to_dict_list(): An error occured ")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
            return None

    def refresh_inventory_to_dict(self, filename):
        logging.debug("VMwareConfigIO(): read_lines_to_dict instantiated")
        result = {}
        invalid_lines = []
        try:
            with open(filename, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or '=' not in line:
                        logging.error("Found line without key/value: " + str(line))
                        invalid_lines.append(line)
                        continue  # Skip empty lines and lines without a separator
                    splitline = line.split(".")
                    name = splitline[0].strip()
                    right = '.'.join(splitline[1:]).strip()
                    if name not in result:
                        result[name] = {}

                    name2 = right.split("=")[0].strip()
                    settingval = line.split("=")[1].strip().replace("\"","")

                    result[name][name2] = settingval
            return result
        except FileNotFoundError:
            logging.error("Error in read_lines_to_dict_list(): File not found: " + str(filename))
            return None
        except Exception:
            logging.error("Error in read_lines_to_dict_list(): An error occured ")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
            return None
        

    def get_vmlist_name(self):
        logging.debug("VMwareConfigIO(): get_vmlist_name instantiated")
        result = []
        vmlist = self.get_matching_keys(self.vminventory_dict, 'vmlist*')
        realvmlist = self.get_keys_with_config(self.vminventory_dict, vmlist, "IsClone")
        for item in realvmlist:
            result.append(self.vminventory_dict[item]['config'])
        return result


    def get_vmnics(self, vmname):
        logging.debug("VMwareConfigIO(): get_vmnics instantiated")
        result = {}

        self.vmconf_dict = self.refresh_inventory_to_dict(vmname)
        ethernetlist = self.get_matching_keys(self.vmconf_dict, 'ethernet*')
        connectionType = self.get_keys_with_config(self.vmconf_dict, ethernetlist, "connectionType")
        for item in connectionType:
            result[item] = self.vmconf_dict[item]['connectionType']

        return result

    def get_vmgroups_name(self):
        logging.debug("VMwareConfigIO(): get_vmgroups_name instantiated")
        groups = {}
        fid = {}
        vmlist = self.get_matching_keys(self.vminventory_dict, "vmlist*")
        folders = self.get_keys_with_config(self.vminventory_dict, vmlist, 'Expanded')
        for f in folders:
            fid[self.vminventory_dict[f]['ItemID']] = self.vminventory_dict[f]['DisplayName']
        vms = self.get_keys_with_config(self.vminventory_dict, vmlist, 'State')
        for vm in vms:
            vm_parent = self.vminventory_dict[vm]['ParentID']
            if vm_parent == "0" or vm_parent not in fid:
                groups[self.vminventory_dict[vm]['config']] = "No Group"
                vm_parent = "0"
            else:
                groups[self.vminventory_dict[vm]['config']] = fid[vm_parent]
        return groups
    
    def get_vmlist_disp2num(self):
        logging.debug("VMwareConfigIO(): get_vmgroups_listnum instantiated")
        result = {}
        #get all vmlist items
        vmlists = self.get_matching_keys(self.vminventory_dict, "vmlist*")
        #get list of VMs
        vms_vmlist = self.get_keys_with_config(self.vminventory_dict, vmlists, "IsClone")
        for vm in vms_vmlist:
            display_name = self.vminventory_dict[vm]["config"]
            result[display_name] = vm
        return result

    def get_vmgroup_disp2num(self):
        logging.debug("VMwareConfigIO(): get_vmgroup_disp2num instantiated")
        result = {}
        #get all vmlist items
        vmlists = self.get_matching_keys(self.vminventory_dict, "vmlist*")
        groups_vmlist = self.get_keys_with_config(self.vminventory_dict, vmlists, "Expanded")
        for group in groups_vmlist:
            display_name = self.vminventory_dict[group]["DisplayName"]
            result[display_name] = group
        return result


'''
def dict_to_dot(d, prefix=''):
    result = {}
    for k, v in d.items():
        if isinstance(v, dict):
            result.update(dict_to_dot(v, prefix + k + '.'))
        else:
            result[prefix + k] = v
    return result

my_dict = {
    'a': 1,
    'b': {
        'c': 2,
        'd': {
            'e': 3
        }
    }
}

print(dict_to_dot(my_dict)) 
'''