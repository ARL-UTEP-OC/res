from gui.Dialogs.GUIFunctionExecutingDialog import GUIFunctionExecutingDialog
from gui.Dialogs.VMRetrievingDialog import VMRetrievingDialog
from gui.Dialogs.VMRetreiveDialog import VMRetrieveDialog
from PyQt5 import QtCore, QtGui, QtWidgets
import logging
from gui.Dialogs.ExperimentActionDialog import ExperimentActionDialog
from gui.Widgets.ExperimentActionsWidgets.ExperimentActionsVMStatusWidget import ExperimentActionsVMStatusWidget
from engine.Configuration.ExperimentConfigIO import ExperimentConfigIO
from engine.Configuration.UserPool import UserPool
from PyQt5.QtWidgets import (QApplication, qApp, QAction, QCheckBox, QComboBox, QDateTimeEdit,
        QDial, QDialog, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
        QProgressBar, QPushButton, QRadioButton, QScrollBar, QSizePolicy,
        QSlider, QSpinBox, QStyleFactory, QMessageBox, QTableWidget, QTabWidget, QTextEdit,
        QVBoxLayout, QWidget, QStackedWidget, QStatusBar, QMenuBar)
from gui.Helpers.ExperimentActions import ExperimentActions
import os

class ExperimentActionsWidget(QtWidgets.QWidget):
    def __init__(self, parent=None, statusBar=None):
        logging.debug("ExperimentActionsWidget instantiated")
        QtWidgets.QWidget.__init__(self, parent=None)
        self.statusBar = statusBar
        self.experimentItemNames = {}
        self.experimentActionsBaseWidgets = {}
        self.eco = ExperimentConfigIO.getInstance()
        self.rolledoutjson = None

        self.setObjectName("ExperimentActionsWidget")

        self.windowWidget = QtWidgets.QWidget()
        self.windowWidget.setObjectName("windowWidget")
        self.windowBoxHLayout = QtWidgets.QHBoxLayout()
        #self.windowBoxHLayout.setContentsMargins(0, 0, 0, 0)
        self.windowBoxHLayout.setObjectName("windowBoxHLayout")
        self.windowWidget.setLayout(self.windowBoxHLayout)

        self.experimentTree = QtWidgets.QTreeWidget(parent)
        self.experimentTree.setObjectName("experimentTree")    
        self.experimentTree.header().resizeSection(0, 150)
        self.experimentTree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.experimentTree.customContextMenuRequested.connect(self.showContextMenu)
        self.experimentTree.itemSelectionChanged.connect(self.onItemSelected)
        self.experimentTree.setEnabled(True)
        self.experimentTree.setMinimumSize(200,521)
        self.experimentTree.setMaximumWidth(350)
        self.experimentTree.setObjectName("experimentTree")
        self.experimentTree.headerItem().setText(0, "Experiments New")
        self.experimentTree.setSortingEnabled(False)
        self.windowBoxHLayout.addWidget(self.experimentTree)

        self.windowBoxVLayout = QtWidgets.QVBoxLayout()
        #self.windowBoxHLayout.setContentsMargins(0, 0, 0, 0)
        self.windowBoxVLayout.setObjectName("windowBoxVLayout")

        self.basedataStackedWidget = QStackedWidget()
        self.basedataStackedWidget.setObjectName("basedataStackedWidget")
        self.basedataStackedWidget.setEnabled(False)
        self.windowBoxVLayout.addWidget(self.basedataStackedWidget)

        self.refreshVMsButton = QtWidgets.QPushButton("Refresh Status")
        self.refreshVMsButton.clicked.connect(self.refreshVMStatus)
        self.refreshVMsButton.setEnabled(False)
        self.windowBoxVLayout.addWidget(self.refreshVMsButton)

        self.windowBoxHLayout.addLayout(self.windowBoxVLayout)

        # Context menus
        self.experimentMenu = QtWidgets.QMenu()
        self.startupContextMenu = QtWidgets.QMenu("Startup")
        self.shutdownContextMenu = QtWidgets.QMenu("Shutdown")
        self.stateContextMenu = QtWidgets.QMenu("State")
        self.controlContextMenu = QtWidgets.QMenu("Control")
        self.experimentMenu.addMenu(self.startupContextMenu)
        self.experimentMenu.addMenu(self.shutdownContextMenu)
        self.experimentMenu.addMenu(self.stateContextMenu)
        self.experimentMenu.addMenu(self.controlContextMenu)

        self.cloneExperiment = self.startupContextMenu.addAction("Signal - Create Clones")
        self.cloneExperiment.triggered.connect(self.menuItemSelected)
        
        self.startVMs = self.startupContextMenu.addAction("Signal - Start VMs (headless)")
        self.startVMs.triggered.connect(self.menuItemSelected)

        self.restoreSnapshots = self.startupContextMenu.addAction("Signal - Restore Snapshots")
        self.restoreSnapshots.triggered.connect(self.menuItemSelected)

        self.pauseVMs = self.shutdownContextMenu.addAction("Signal - Pause VMs")
        self.pauseVMs.triggered.connect(self.menuItemSelected)

        self.suspendVMs = self.shutdownContextMenu.addAction("Signal - Suspend & Save States")
        self.suspendVMs.triggered.connect(self.menuItemSelected)

        self.poweroffVMs = self.shutdownContextMenu.addAction("Signal - Power Off VMs")
        self.poweroffVMs.triggered.connect(self.menuItemSelected)

        self.deleteClones = self.shutdownContextMenu.addAction("Signal - Delete Clones")
        self.deleteClones.triggered.connect(self.menuItemSelected)
        self.shutdownContextMenu.addAction(self.deleteClones)

        self.snapshotVMs = self.stateContextMenu.addAction("Signal - Snapshot VMs")
        self.snapshotVMs.triggered.connect(self.menuItemSelected)

        self.guestCmdsVMs = self.controlContextMenu.addAction("Signal - Run Startup GuestCmds")
        self.guestCmdsVMs.triggered.connect(self.menuItemSelected)

        self.guestAdhocCmdsVMs = self.controlContextMenu.addAction("Signal - Run Stored GuestCmds")
        self.guestAdhocCmdsVMs.triggered.connect(self.menuItemSelected)

        self.setLayout(self.windowBoxHLayout)
        self.retranslateUi()

    def retranslateUi(self):
        logging.debug("ExperimentActionsWidget: retranslateUi(): instantiated")
        self.setWindowTitle("ExperimentActionsWidget")
        self.experimentTree.headerItem().setText(0, "Experiments")
        self.experimentTree.setSortingEnabled(False)
    
    def onItemSelected(self):
        logging.debug("MainApp:onItemSelected instantiated")
        self.basedataStackedWidget.setEnabled(True)
        self.refreshVMsButton.setEnabled(True)
    	# Get the selected item
        selectedItem = self.experimentTree.currentItem()
        if selectedItem == None:
            logging.debug("MainApp:onItemSelected no configurations left")
            self.statusBar.showMessage("No configuration items selected or available.")
            return

        #Check if it's the case that an experiment name was selected
        parentparentSelectedItem = None
        parentSelectedItem = selectedItem.parent()
        if parentSelectedItem != None:
            parentparentSelectedItem = selectedItem.parent().parent()
            
        if parentSelectedItem == None:
            #A base widget was selected - not sure why this causes a 'KeyError" sometimes... hard to replicate
            self.basedataStackedWidget.setCurrentWidget(self.experimentActionsBaseWidgets[selectedItem.text(0)]["ExperimentActionsBaseWidget"])
            self.experimentTree.resizeColumnToContents(0)
        elif parentparentSelectedItem == None:
            #A base widget was selected
            self.basedataStackedWidget.setCurrentWidget(self.experimentActionsBaseWidgets[parentSelectedItem.text(0)]["ExperimentActionsBaseWidget"])
            self.experimentTree.resizeColumnToContents(0)
        else:
            #Check if it's the case that a VM Name was selected
            if(selectedItem.text(0)[0] == "V"):
                logging.debug("Setting right widget: " + str(self.experimentActionsBaseWidgets[parentparentSelectedItem.text(0)]["ExperimentActionsVMWidgets"][selectedItem.text(0)]))
                self.basedataStackedWidget.setCurrentWidget(self.experimentActionsBaseWidgets[parentparentSelectedItem.text(0)]["ExperimentActionsVMWidgets"][selectedItem.text(0)])
            if(selectedItem.text(0)[0] == "S"):
                logging.debug("Setting right widget: " + str(self.experimentActionsBaseWidgets[parentparentSelectedItem.text(0)]["ExperimentActionsSetWidgets"][selectedItem.text(0)]))
                self.basedataStackedWidget.setCurrentWidget(self.experimentActionsBaseWidgets[parentparentSelectedItem.text(0)]["ExperimentActionsSetWidgets"][selectedItem.text(0)])
            if(selectedItem.text(0)[0] == "T"):
                logging.debug("Setting right widget: " + str(self.experimentActionsBaseWidgets[parentparentSelectedItem.text(0)]["ExperimentActionsTemplateWidgets"][selectedItem.text(0)]))
                self.basedataStackedWidget.setCurrentWidget(self.experimentActionsBaseWidgets[parentparentSelectedItem.text(0)]["ExperimentActionsTemplateWidgets"][selectedItem.text(0)])
            if(selectedItem.text(0)[0] == "U"):
                logging.debug("Setting right widget: " + str(self.experimentActionsBaseWidgets[parentparentSelectedItem.text(0)]["ExperimentActionsUserWidgets"][selectedItem.text(0)]))
                self.basedataStackedWidget.setCurrentWidget(self.experimentActionsBaseWidgets[parentparentSelectedItem.text(0)]["ExperimentActionsUserWidgets"][selectedItem.text(0)])


    def getExperimentVMRolledOut(self, configname, config_json):
        logging.debug("ExperimentActionsWidget(): getExperimentVMRolledOut(): retranslateUi(): instantiated")
        self.rolledoutjson = self.eco.getExperimentVMRolledOut(configname, config_json)

    def addExperimentItem(self, configname, config_jsondata=None):
        logging.debug("addExperimentItem(): retranslateUi(): instantiated")
        if configname in self.experimentItemNames:
            logging.error("addExperimentItem(): Item already exists in tree: " + str(configname))
            return
        userpool = UserPool()
        ##Now add the item to the tree widget and create the baseWidget
        experimentTreeWidgetItem = QtWidgets.QTreeWidgetItem(self.experimentTree)
        experimentTreeWidgetItem.setText(0,configname)

        experimentSetTreeItem = QtWidgets.QTreeWidgetItem(experimentTreeWidgetItem)
        experimentSetTreeItem.setText(0,"Sets")

        experimentCloneTreeItem = QtWidgets.QTreeWidgetItem(experimentTreeWidgetItem)
        experimentCloneTreeItem.setText(0,"Templates")

        experimentVMTreeItem = QtWidgets.QTreeWidgetItem(experimentTreeWidgetItem)
        experimentVMTreeItem.setText(0,"VMs")

        experimentUserTreeItem = QtWidgets.QTreeWidgetItem(experimentTreeWidgetItem)
        experimentUserTreeItem.setText(0,"Users")

        self.experimentItemNames[configname] = experimentTreeWidgetItem
        #get all rolled out and then get them by VM
        if config_jsondata == None or "vm" not in config_jsondata['xml']['testbed-setup']['vm-set']:
            experimentTreeWidgetItem.setDisabled(True)
            experimentTreeWidgetItem.setText(0,configname+" (No VMs Added to Experiment)")
            return
        
        funcs = []
        funcs.append((self.getExperimentVMRolledOut, configname, config_jsondata))
        GUIFunctionExecutingDialog(None, "Processing VMs for " + str(configname), funcs).exec_()
        rolledoutjson = self.rolledoutjson
        if rolledoutjson != None:
            # if file was specified, but it doesn't exist, prepend usernames
            invalid_userfile = False
            users_filename = config_jsondata["xml"]["testbed-setup"]["vm-set"]["users-filename"]
            if users_filename != None and users_filename.strip() != "":
                if os.path.exists(users_filename) == False:
                    invalid_userfile = True
            #get the usersConn associations first:            
            usersConns = userpool.generateUsersConns(configname, creds_file=users_filename, rolledout_json=rolledoutjson)
            vmuser_mapping = {}
            for (username, password) in usersConns:
                for conn in usersConns[(username, password)]:
                    cloneVMName = conn[0]
                    if invalid_userfile == False:
                        vmuser_mapping[cloneVMName] = (username, password)
                    else:
                        vmuser_mapping[cloneVMName] = "userfile_not_found"
                    
            #create the status widgets (tables)
            self.experimentActionsBaseWidget = ExperimentActionsVMStatusWidget(self, configname, rolledoutjson=rolledoutjson, interest_vmnames=[], vmuser_mapping=vmuser_mapping, status_bar=self.statusBar)
            self.experimentActionsBaseWidgets[configname] = {"ExperimentActionsBaseWidget": {}, "ExperimentActionsSetWidgets": {}, "ExperimentActionsTemplateWidgets": {}, "ExperimentActionsVMWidgets": {}, "ExperimentActionsUserWidgets": {} }
            self.experimentActionsBaseWidgets[configname]["ExperimentActionsBaseWidget"] = self.experimentActionsBaseWidget
            self.basedataStackedWidget.addWidget(self.experimentActionsBaseWidget)
            #Set-based view
            (template_vms, num_clones) = rolledoutjson
            #First create the sets from the rolled out data
            sets = self.eco.getExperimentSetDictFromRolledOut(configname, rolledoutjson)
            for set in sets:
                set_item = QtWidgets.QTreeWidgetItem(experimentSetTreeItem)
                setlabel = "S: Set " + set
                set_item.setText(0,setlabel)
                # Set Widget
                experimentActionsSetStatusWidget = ExperimentActionsVMStatusWidget(self, configname, rolledoutjson=rolledoutjson, interest_vmnames=sets[set], vmuser_mapping=vmuser_mapping, status_bar=self.statusBar)
                self.experimentActionsBaseWidgets[configname]["ExperimentActionsSetWidgets"][setlabel] = experimentActionsSetStatusWidget
                self.basedataStackedWidget.addWidget(experimentActionsSetStatusWidget)

            templates = self.eco.getExperimentVMNamesFromTemplateFromRolledOut(configname, rolledoutjson)
            for templatename in templates:
                template_item = QtWidgets.QTreeWidgetItem(experimentCloneTreeItem)
                templatelabel = "T: " + templatename
                template_item.setText(0,templatelabel)
                # Set Widget
                experimentActionsTemplateStatusWidget = ExperimentActionsVMStatusWidget(self, configname, rolledoutjson=rolledoutjson, interest_vmnames=templates[templatename], vmuser_mapping=vmuser_mapping, status_bar=self.statusBar)
                self.experimentActionsBaseWidgets[configname]["ExperimentActionsTemplateWidgets"][templatelabel] = experimentActionsTemplateStatusWidget
                self.basedataStackedWidget.addWidget(experimentActionsTemplateStatusWidget)

            #Individual VM-based view
            vms_list = self.eco.getExperimentVMListsFromRolledOut(configname, rolledoutjson)
            for vm in vms_list:
                vmname = vm["name"]
                vm_item = QtWidgets.QTreeWidgetItem(experimentVMTreeItem)
                vmlabel = "V: " + vmname
                vm_item.setText(0,vmlabel)
                # VM Config Widget
                experimentActionsVMStatusWidget = ExperimentActionsVMStatusWidget(self, configname, rolledoutjson=rolledoutjson, interest_vmnames=[vmname], vmuser_mapping=vmuser_mapping, status_bar=self.statusBar)
                self.experimentActionsBaseWidgets[configname]["ExperimentActionsVMWidgets"][vmlabel] = experimentActionsVMStatusWidget
                self.basedataStackedWidget.addWidget(experimentActionsVMStatusWidget)

            #Individual Users-based view
            num = 1
            for (username, password) in usersConns:
                vmnames = [tuple[0] for tuple in usersConns[(username, password)] ]
                user_item = QtWidgets.QTreeWidgetItem(experimentUserTreeItem)
                user_label = "U: " + username + " (Set " + str(num) + ")"
                num+=1
                user_item.setText(0,user_label)
                # VM Config Widget
                experimentActionsUserStatusWidget = ExperimentActionsVMStatusWidget(self, configname, rolledoutjson=rolledoutjson, interest_vmnames=vmnames, vmuser_mapping=vmuser_mapping, status_bar=self.statusBar)
                self.experimentActionsBaseWidgets[configname]["ExperimentActionsUserWidgets"][user_label] = experimentActionsUserStatusWidget
                self.basedataStackedWidget.addWidget(experimentActionsUserStatusWidget)
        else:
            experimentTreeWidgetItem.setDisabled(True)
        self.statusBar.showMessage("Added new experiment: " + str(configname))
        logging.debug("addExperimentItem(): retranslateUi(): Completed")

    def resetExperiment(self, configname, config_jsondata):
        logging.debug("updateExperimentItem(): retranslateUi(): instantiated")
        if configname not in self.experimentItemNames:
            logging.error("removeExperimentItem(): Item does not exist in tree: " + str(configname))
            return
        self.removeExperimentItem(configname)
        self.addExperimentItem(configname, config_jsondata)

    def removeExperimentItem(self, configname):
        logging.debug("removeExperimentItem(): retranslateUi(): instantiated")
        if configname not in self.experimentItemNames:
            logging.error("removeExperimentItem(): Item does not exist in tree: " + str(configname))
            return
        experimentTreeWidgetItem = self.experimentItemNames[configname]
        self.experimentTree.invisibleRootItem().removeChild(experimentTreeWidgetItem)
        del self.experimentItemNames[configname]
        logging.debug("removeExperimentItem(): Completed")

    def showContextMenu(self, position):
        logging.debug("ExperimentActionsWidget(): showContextMenu(): instantiated")
        self.experimentMenu.popup(self.experimentTree.mapToGlobal(position))

    def getTypeNameFromSelection(self):
        configname = ""
        itype = ""
        name = ""
        #configname selected
        if self.experimentTree.currentItem().parent() == None:
            configname = self.experimentTree.currentItem().text(0)
            itype = "set"
            name = "all"
        #sets, clones, or VMs label selected
        elif self.experimentTree.currentItem().parent().parent() == None:
            configname = self.experimentTree.currentItem().parent().text(0)
            itype = "set"
            name = "all"
        #specific item selected
        elif self.experimentTree.currentItem().parent().parent().parent() == None:
            configname = self.experimentTree.currentItem().parent().parent().text(0)
            currItemText = self.experimentTree.currentItem().text(0)
            if currItemText.startswith("S: Set "):
                itype = "set"
                name = currItemText.split("S: Set ")[1:]
                name = " ".join(name)
            elif currItemText.startswith("V: "):
                itype = "vm"
                name = currItemText.split("V: ")[1:]
                name = "\"" + " ".join(name) + "\""
            elif currItemText.startswith("T: "):
                itype = "template"
                name = currItemText.split("T: ")[1:]
                name = "\"" + " ".join(name) + "\""
            elif currItemText.startswith("U: "):
                itype = "set"
                name = currItemText.split("(Set ")[1].split(")")[0:-1]
                name = " ".join(name)
        return configname, itype, name

    def menuItemSelected(self):
        logging.debug("menuItemSelected(): instantiated")
        actionlabelname = self.sender().text()
        configname, itype, name = self.getTypeNameFromSelection()
        ExperimentActions().experimentActionEvent(configname, actionlabelname, itype, name)
        self.statusBar.showMessage("Executed " + str(actionlabelname) + " on " + configname)

    def refreshVMStatus(self):
        logging.debug("refreshVMStatus(): instantiated")

        #Get the configname based on selected item:
        selectedItem = self.experimentTree.currentItem()
        #Check if an experiment name is selected
        if selectedItem == None:
            logging.error("No experiment label was selected.")
            return

        #If so, get the configname associated with it
        while selectedItem.parent() != None:
            selectedItem = selectedItem.parent()
        configname = selectedItem.text(0)
        s = VMRetrievingDialog(self, configname).exec_()
        self.vms = s["vmstatus"]

        #Update all vm status in the subtrees
        #First the "all" view
        for widget in self.experimentActionsBaseWidgets[configname].values():
            if isinstance(widget, ExperimentActionsVMStatusWidget):
                widget.updateVMStatus(self.vms)
        #The Sets:
        for widget in self.experimentActionsBaseWidgets[configname]["ExperimentActionsSetWidgets"].values():
            if isinstance(widget, ExperimentActionsVMStatusWidget):
                widget.updateVMStatus(self.vms)
        #The Templates:
        for widget in self.experimentActionsBaseWidgets[configname]["ExperimentActionsTemplateWidgets"].values():
            if isinstance(widget, ExperimentActionsVMStatusWidget):
                widget.updateVMStatus(self.vms)
        #The VMs
        for widget in self.experimentActionsBaseWidgets[configname]["ExperimentActionsVMWidgets"].values():
            if isinstance(widget, ExperimentActionsVMStatusWidget):
                widget.updateVMStatus(self.vms)
        #The Users
        for widget in self.experimentActionsBaseWidgets[configname]["ExperimentActionsUserWidgets"].values():
            if isinstance(widget, ExperimentActionsVMStatusWidget):
                widget.updateVMStatus(self.vms)