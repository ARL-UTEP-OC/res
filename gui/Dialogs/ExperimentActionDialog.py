from PyQt5.QtWidgets import QFileDialog, QWidget
from gui.Dialogs.ExperimentActioningDialog import ExperimentActioningDialog
from engine.Configuration.SystemConfigIO import SystemConfigIO

from engine.Configuration.SystemConfigIO import SystemConfigIO
from PyQt5.QtCore import QDateTime, Qt, QTimer, QThread, pyqtSignal, QObject
from PyQt5.QtWidgets import (QApplication, QCheckBox, QComboBox, QDateTimeEdit,
        QDial, QDialog, QDialogButtonBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
        QProgressBar, QPushButton, QRadioButton, QScrollBar, QSizePolicy,
        QSlider, QSpinBox, QStyleFactory, QTableWidget, QTabWidget, QTextEdit,
        QVBoxLayout, QWidget, QMessageBox)

from engine.Engine import Engine
from engine.Manager.ExperimentManage.ExperimentManage import ExperimentManage
from engine.Configuration.ExperimentConfigIO import ExperimentConfigIO
from gui.Dialogs.ExperimentActioningDialog import ExperimentActioningDialog
import logging
from engine.Configuration.UserPool import UserPool



import os
import logging

class ExperimentActionDialog(QDialog):
    
    def __init__(self, parent, configname, actionname, itype="", name=""):
        logging.debug("ExperimentActionDialog(): instantiated")
        super(ExperimentActionDialog, self).__init__(parent)
        self.parent = parent
        self.eco = ExperimentConfigIO.getInstance()
        vmHostname, rdpBrokerHostname, chatServerIP, challengesServerIP, users_file = self.eco.getExperimentServerInfo(configname)
        self.s = SystemConfigIO()
        self.configname = configname
        self.actionname = actionname
        self.experimentHostname = vmHostname
        self.usersFile = users_file
        self.itype = itype
        self.name = name
        if vmHostname.strip() == "":
            self.experimentHostname = ""
            self.setEnabled(False)
        else:
            self.experimentHostname = vmHostname
        self.em = ExperimentManage()
        self.setMinimumWidth(350)

        self.createFormGroupBox()
        
        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)
        
        mainLayout = QVBoxLayout()
        mainLayout.addWidget(self.formGroupBox)
        mainLayout.addWidget(buttonBox)
        self.setLayout(mainLayout)
        
        self.setWindowTitle(str(actionname) + " Experiment")
        
    def createFormGroupBox(self):
        self.formGroupBox = QGroupBox("Experiment Information")
        self.layout = QFormLayout()
        self.experimentHostnameLineEdit = QLineEdit(self.experimentHostname)
        self.experimentHostnameLineEdit.setEnabled(False)
        self.layout.addRow(QLabel("VM Server URL:"), self.experimentHostnameLineEdit)
        mgmusername = ""
        mgmpassword = ""
        cachedCreds = self.eco.getConfigExperimentExecCreds(self.configname)
        if cachedCreds != None:
            mgmusername = cachedCreds[0]
            mgmpassword = cachedCreds[1]
            
        self.usernameLineEdit = QLineEdit(mgmusername)
        self.passwordLineEdit = QLineEdit(mgmpassword)
        self.passwordLineEdit.setEchoMode(QLineEdit.Password)
        if self.actionname != "Open":
            self.layout.addRow(QLabel("Management Username:"), self.usernameLineEdit)
            self.layout.addRow(QLabel("Management Password:"), self.passwordLineEdit)
        
        self.formGroupBox.setLayout(self.layout)

    def exec_(self):
        logging.debug("ExperimentActionDialog(): exec_() instantiated")
        result = super(ExperimentActionDialog, self).exec_()
        if str(result) == str(1):
            logging.debug("dialog_response(): OK was pressed")

            self.eco.storeConfigExperimentExecCreds(self.configname, self.usernameLineEdit.text(), self.passwordLineEdit.text())
            cad = ExperimentActioningDialog(self.parent, self.configname, self.actionname, self.itype, self.name, self.usernameLineEdit.text(), self.passwordLineEdit.text()).exec_()
            return (QMessageBox.Ok)
        return (QMessageBox.Cancel)

    # def experimentActionDialog(self, configname, actionname, itype="", name=""):
    #     logging.debug("experimentActionDialog(): Instantiated")
    #     self.configname = configname
    #     self.s = SystemConfigIO()
    #     self.destinationPath = os.path.join(self.s.getConfig()['EXPERIMENTS']['EXPERIMENTS_PATH'])
    #     ouputstr = self.experimentAction(actionname, itype, name)
    #     logging.debug("experimentActionDialog(): Completed")
    #     return ouputstr

    # def experimentAction(self, actionname, itype, name):
    #     logging.debug("experimentAction(): instantiated")
    #     status, outputstr = ExperimentActioningDialog(None, self.configname, actionname, itype, name).exec_()
    #     return outputstr