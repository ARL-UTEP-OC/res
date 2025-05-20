import logging
from gui.Dialogs.KeycloakActionDialog import KeycloakActionDialog

class ConnectionActions():

    def connectionActionEvent(self, parent, configname, actionlabelname, vmHostname, users_file="", itype="", name=""):
        logging.debug("connectionActionEvent(): showContextMenu(): instantiated")
        if "Create Users" in actionlabelname:
            self.connectionAction(parent, configname, "Add", vmHostname, users_file, itype, name)
        elif "Remove Users" in actionlabelname:
            self.connectionAction(parent, configname, "Remove", vmHostname, users_file, itype, name)
        elif "Clear All Users on Server" in actionlabelname:
            self.connectionAction(parent, configname, "Clear", vmHostname, users_file, itype, name)

    def connectionAction(self, parent, configname, actionname, vmHostname, users_file, itype, name):
        logging.debug("connnectionAction(): showContextMenu(): instantiated")
        KeycloakActionDialog(parent, configname, actionname, vmHostname, users_file, itype, name).exec_()