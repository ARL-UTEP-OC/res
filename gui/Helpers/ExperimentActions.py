import logging
from gui.Dialogs.ExperimentActionDialog import ExperimentActionDialog

class ExperimentActions():

    def experimentActionEvent(self, parent, configname, actionlabelname, itype, name):
        logging.debug("cloneExperimentActionEvent(): showContextMenu(): instantiated")
        if "Signal - Create Clone" in actionlabelname:
            self.experimentAction(parent, configname, "Create Experiment", itype, name)
        elif "Signal - Start VM" in actionlabelname:
            self.experimentAction(parent, configname, "Start Experiment", itype, name)
        elif "Signal - Suspend & Save State" in actionlabelname:
            self.experimentAction(parent, configname, "Suspend Experiment", itype, name)
        elif "Signal - Pause VM" in actionlabelname:
            self.experimentAction(parent, configname, "Pause Experiment", itype, name)
        elif "Signal - Restore Snapshot" in actionlabelname:
            self.experimentAction(parent, configname, "Restore Experiment", itype, name)
        elif "Signal - Snapshot VM" in actionlabelname:
            self.experimentAction(parent, configname, "Snapshot Experiment", itype, name)
        elif "Signal - Delete Clone" in actionlabelname:
            self.experimentAction(parent, configname, "Remove Experiment", itype, name)            
        elif "Signal - Power Off VM" in actionlabelname:
            self.experimentAction(parent, configname, "Stop Experiment", itype, name)
        elif "Signal - Run Startup GuestCmds" in actionlabelname:
            self.experimentAction(parent, configname, "Run GuestCmds", itype, name)
        elif "Signal - Run Stored GuestCmds" in actionlabelname:
            self.experimentAction(parent, configname, "Run GuestStored", itype, name)

    def experimentAction(self, parent, configname, actionname, itype, name):
        logging.debug("experimentAction(): showContextMenu(): instantiated")
        ExperimentActionDialog(parent, configname, actionname, itype, name).exec_()