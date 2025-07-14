from engine.Configuration.SystemConfigIO import SystemConfigIO
from gui.Dialogs.KeycloakOpeningDialog import KeycloakOpeningDialog
from gui.Dialogs.KeycloakRetrievingDialog import KeycloakRetrievingDialog
from PyQt5.QtCore import QDateTime, Qt, QTimer, QThread, pyqtSignal, QObject
from PyQt5.QtWidgets import (QApplication, QCheckBox, QComboBox, QDateTimeEdit,
        QDial, QDialog, QDialogButtonBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
        QProgressBar, QPushButton, QRadioButton, QScrollBar, QSizePolicy,
        QSlider, QSpinBox, QStyleFactory, QTableWidget, QTabWidget, QTextEdit,
        QVBoxLayout, QWidget, QMessageBox)

from engine.Engine import Engine
from engine.Manager.ConnectionManage.ConnectionManage import ConnectionManage
from engine.Configuration.ExperimentConfigIO import ExperimentConfigIO
from gui.Dialogs.KeycloakActioningDialog import KeycloakActioningDialog
import logging
from engine.Configuration.UserPool import UserPool

class KeycloakActionDialog(QDialog):

    def __init__(self, parent, configname, actionname, keycloakserver, users_file="", itype="", name=""):
        logging.debug("KeycloakActionDialog(): instantiated")
        super(KeycloakActionDialog, self).__init__(parent)
        self.parent = parent
        self.eco = ExperimentConfigIO.getInstance()
        self.s = SystemConfigIO()
        self.configname = configname
        self.actionname = actionname
        self.keycloakserver = keycloakserver
        self.usersFile = users_file
        self.itype = itype
        self.name = name
        self.cm = ConnectionManage()
        self.setMinimumWidth(450)

        self.createFormGroupBox()
        
        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)
        
        mainLayout = QVBoxLayout()
        mainLayout.addWidget(self.formGroupBox)
        mainLayout.addWidget(buttonBox)
        self.setLayout(mainLayout)
        
        self.setWindowTitle(str(actionname) + " Connection")
        
    def createFormGroupBox(self):
        self.formGroupBox = QGroupBox("Connection Information")
        self.layout = QFormLayout()
        self.keycloakserverLineEdit = QLineEdit(self.keycloakserver)
        self.keycloakserverLineEdit.setEnabled(False)
        self.layout.addRow(QLabel("Keycloak Server URL:"), self.keycloakserverLineEdit)

        mgmusername = ""
        mgmpassword = ""
        cachedCreds = self.eco.getConfigKeycloakCreds(self.configname)
        if cachedCreds != None:
            mgmusername = cachedCreds[0]
            mgmpassword = cachedCreds[1]
            
        self.usernameLineEdit = QLineEdit(mgmusername)
        self.passwordLineEdit = QLineEdit(mgmpassword)
        self.passwordLineEdit.setEchoMode(QLineEdit.Password)
        self.layout.addRow(QLabel("Management Username:"), self.usernameLineEdit)
        self.layout.addRow(QLabel("Management Password:"), self.passwordLineEdit)
        
        self.maxConnectionsLineEdit = QLineEdit("10")
        self.heightLineEdit = QLineEdit("1400")
        self.widthLineEdit = QLineEdit("1050")
        self.bitdepthComboBox = QComboBox()
        self.bitdepthComboBox.addItem("256 colors (8-bit)")
        self.bitdepthComboBox.addItem("Low color (16-bit)")
        self.bitdepthComboBox.addItem("True color (24-bit)")
        self.bitdepthComboBox.addItem("True color (32-bit)")
        self.bitdepthComboBox.setCurrentIndex(1)

        self.usersFileLabel = QLineEdit(self.usersFile)
        self.usersFileLabel.setEnabled(False)
        if self.actionname == "Add":
            #Need to make a function to create more than one user to a single instance 
            self.layout.addRow(QLabel("Users File: "), self.usersFileLabel)
            # self.layout.addRow(QLabel("Max Connections Per User:"), self.maxConnectionsLineEdit)      
            # self.layout.addRow(QLabel("Display Height:"), self.heightLineEdit)
            # self.layout.addRow(QLabel("Display Width:"), self.widthLineEdit)
            # self.layout.addRow(QLabel("Bit Depth:"), self.bitdepthComboBox)
        if self.actionname == "Remove":
            self.layout.addRow(QLabel("Users File: "), self.usersFileLabel)
        self.formGroupBox.setLayout(self.layout)

    def exec_(self):
        logging.debug("KeycloakActionDialog(): exec_() instantiated")
        result = super(KeycloakActionDialog, self).exec_()
        if str(result) == str(1):
            logging.debug("dialog_response(): OK was pressed")
            if self.actionname == "Add":
                self.args = [self.keycloakserverLineEdit.text(), self.usernameLineEdit.text(), self.passwordLineEdit.text(), self.usersFileLabel.text(), self.itype, self.name]
            elif self.actionname == "Remove":
                self.args = [self.keycloakserverLineEdit.text(), self.usernameLineEdit.text(), self.passwordLineEdit.text(), self.usersFileLabel.text(), self.itype, self.name]
            elif self.actionname == "Clear":
                self.args = [self.keycloakserverLineEdit.text(), self.usernameLineEdit.text(), self.passwordLineEdit.text()]
            elif self.actionname == "Refresh":
                self.args = [self.keycloakserverLineEdit.text(), self.usernameLineEdit.text(), self.passwordLineEdit.text()]
            elif self.actionname == "Open":
                #get all of the connections from the currently selected item
                userpool = UserPool()
                usersConns = userpool.generateUsersConns(self.configname, creds_file=self.usersFile)
                vmuser_mapping = {}
                for (username, password) in usersConns:
                    for conn in usersConns[(username, password)]:
                        cloneVMName = conn[0]
                        vmuser_mapping[cloneVMName] = (username, password)
                #get all vms based on what's selected
                tentativeVMs = self.eco.getValidVMsFromTypeName(self.configname, self.itype, self.name)
                #get user/password from selected vms and store those in the list of users to open
                usersToOpen = {}
                for vm in tentativeVMs:
                    if vm in vmuser_mapping:
                        usersToOpen[vmuser_mapping[vm]] = True
                logging.debug(str(usersToOpen))
            else:
                pass
            if self.actionname == "Refresh":
                self.eco.storeConfigKeycloakCreds(self.configname, self.usernameLineEdit.text(), self.passwordLineEdit.text())
                crd = KeycloakRetrievingDialog(self.parent, self.configname, self.args).exec_()
                return crd
            else:
                self.eco.storeConfigKeycloakCreds(self.configname, self.usernameLineEdit.text(), self.passwordLineEdit.text())
                cad = KeycloakActioningDialog(self.parent, self.configname, self.actionname, self.args).exec_()
                return (QMessageBox.Ok)
        return (QMessageBox.Cancel)