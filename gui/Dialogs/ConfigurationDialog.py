from PyQt5.QtCore import QDateTime, Qt, QTimer, QThread, pyqtSignal, QObject
from PyQt5.QtWidgets import (QApplication, QCheckBox, QComboBox, QDateTimeEdit, 
        QDial, QDialog, QDialogButtonBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
        QProgressBar, QPushButton, QRadioButton, QScrollBar, QSizePolicy,
        QSlider, QSpinBox, QStyleFactory, QTableWidget, QTabWidget, QTextEdit,
        QVBoxLayout, QWidget, QMessageBox, QFrame, QButtonGroup)

import time
from engine.Configuration.SystemConfigIO import SystemConfigIO
import logging

class ConfigurationDialog(QDialog):

    def __init__(self, parent):
        logging.debug("ConfigurationDialog(): instantiated")
        super(ConfigurationDialog, self).__init__(parent)      
        self.parent = parent
        self.s = SystemConfigIO()
        self.setMinimumWidth(625)

        self.createFormGroupBox()
        
        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)
        
        mainLayout = QVBoxLayout()
        mainLayout.addWidget(self.formGroupBox)
        mainLayout.addWidget(buttonBox)
        self.setLayout(mainLayout)
        
        self.setWindowTitle("RES Configuration")
        
    def createFormGroupBox(self):
        self.formGroupBox = QGroupBox("Configuration Paths (Changes take effect after restart)")
        self.layout = QFormLayout()
        #VirtualBox stuff
        self.virtualboxPathLineEdit = QLineEdit(self.s.getConfig()["VBOX"]["VBOX_PATH"])
        self.layout.addRow(QLabel("VirtualBox Path:"), self.virtualboxPathLineEdit)
        self.vmanagePathLineEdit = QLineEdit(self.s.getConfig()["VBOX"]["VMANAGE_PATH"])
        self.layout.addRow(QLabel("VBoxManage Path:"), self.vmanagePathLineEdit)

        separator1 = QFrame()
        separator1.setFrameShape(QFrame.HLine)
        separator1.setFrameShadow(QFrame.Sunken)
        self.layout.addRow(separator1)
    
        #VMware stuff
        self.vmwarePathLineEdit = QLineEdit(self.s.getConfig()['VMWARE']['VMWARE_PATH'])
        self.layout.addRow(QLabel("VMware Path:"), self.vmwarePathLineEdit)
        self.vmwareVMPathLineEdit = QLineEdit(self.s.getConfig()['VMWARE']['VMANAGE_VM_PATH'])
        self.layout.addRow(QLabel("VMware VMs Path:"), self.vmwareVMPathLineEdit)
        self.vmwareCliPathLineEdit = QLineEdit(self.s.getConfig()['VMWARE']['VMANAGE_CLI_PATH'])
        self.layout.addRow(QLabel("vmcli Path:"), self.vmwareCliPathLineEdit)
        self.vmwareRunPathLineEdit = QLineEdit(self.s.getConfig()['VMWARE']['VMANAGE_RUN_PATH'])
        self.layout.addRow(QLabel("vmrun Path:"), self.vmwareRunPathLineEdit)
        self.vmwareOVFPathLineEdit = QLineEdit(self.s.getConfig()['VMWARE']['VMANAGE_OVF_PATH'])
        self.layout.addRow(QLabel("OVF Tool Path:"), self.vmwareOVFPathLineEdit)
        self.vmwarePrefsPathLineEdit = QLineEdit(self.s.getConfig()['VMWARE']['VMWARE_PREFSFILE_PATH'])
        self.layout.addRow(QLabel("Preferences File Path:"), self.vmwarePrefsPathLineEdit)
        self.vmwareInvPathLineEdit = QLineEdit(self.s.getConfig()['VMWARE']['VMWARE_INVENTORYFILE_PATH'])
        self.layout.addRow(QLabel("Inventory File Path:"), self.vmwareInvPathLineEdit)

        separator2 = QFrame()
        separator2.setFrameShape(QFrame.HLine)
        separator2.setFrameShadow(QFrame.Sunken)
        self.layout.addRow(separator2)

        #Proxmox stuff
        self.proxmoxVMPathLineEdit = QLineEdit(self.s.getConfig()['PROXMOX']['VMANAGE_VMCONF_PATH'])
        self.layout.addRow(QLabel("Proxmox VM Config Path:"), self.proxmoxVMPathLineEdit)
        self.proxmoxQMPathLineEdit = QLineEdit(self.s.getConfig()['PROXMOX']['VMANAGE_QM_PATH'])
        self.layout.addRow(QLabel("qm Path:"), self.proxmoxQMPathLineEdit)
        self.proxmoxPVESHPathLineEdit = QLineEdit(self.s.getConfig()['PROXMOX']['VMANAGE_PVESH_PATH'])
        self.layout.addRow(QLabel("pvesh Path:"), self.proxmoxPVESHPathLineEdit)
        self.proxmoxQMRestorePathLineEdit = QLineEdit(self.s.getConfig()['PROXMOX']['VMANAGE_QMRESTORE_PATH'])
        self.layout.addRow(QLabel("qmrestore Path:"), self.proxmoxQMRestorePathLineEdit)
        self.proxmoxStorageVolLineEdit = QLineEdit(self.s.getConfig()['PROXMOX']['VMANAGE_STORAGE_VOL'])
        self.layout.addRow(QLabel("Storage Volume:"), self.proxmoxStorageVolLineEdit)
        self.proxmoxNodeNameLineEdit = QLineEdit(self.s.getConfig()['PROXMOX']['VMANAGE_NODE_NAME'])
        self.layout.addRow(QLabel("Node Name:"), self.proxmoxNodeNameLineEdit)
        self.proxmoxServerLineEdit = QLineEdit(self.s.getConfig()['PROXMOX']['VMANAGE_SERVER'])
        self.layout.addRow(QLabel("Proxmox Server:"), self.proxmoxServerLineEdit)
        self.proxmoxApiPortLineEdit = QLineEdit(self.s.getConfig()['PROXMOX']['VMANAGE_APIPORT'])
        self.layout.addRow(QLabel("Proxmox API Port:"), self.proxmoxApiPortLineEdit)
        self.proxmoxCmdPortLineEdit = QLineEdit(self.s.getConfig()['PROXMOX']['VMANAGE_CMDPORT'])
        self.layout.addRow(QLabel("Proxmox Command Port:"), self.proxmoxCmdPortLineEdit)
        self.proxmoxMaxCreateJobsLineEdit = QLineEdit(self.s.getConfig()['PROXMOX']['VMANAGE_MAXCREATEJOBS'])
        self.layout.addRow(QLabel("Max Create Jobs:"), self.proxmoxMaxCreateJobsLineEdit)
        self.proxmoxSnapWaitTimeLineEdit = QLineEdit(self.s.getConfig()['PROXMOX']['VMANAGE_SNAPWAITTIME'])
        self.layout.addRow(QLabel("Snapshot Wait Time:"), self.proxmoxSnapWaitTimeLineEdit)

        separator3 = QFrame()
        separator3.setFrameShape(QFrame.HLine)
        separator3.setFrameShadow(QFrame.Sunken)
        self.layout.addRow(separator3)

        self.browserPathLineEdit = QLineEdit(self.s.getConfig()['BROWSER']['BROWSER_PATH'])
        self.layout.addRow(QLabel("Browser Path:"), self.browserPathLineEdit)

        self.experimentPathLineEdit = QLineEdit(self.s.getConfig()["EXPERIMENTS"]["EXPERIMENTS_PATH"])
        self.layout.addRow(QLabel("Experiments Data Path:"), self.experimentPathLineEdit)
        self.temporaryPathLineEdit = QLineEdit(self.s.getConfig()["EXPERIMENTS"]["TEMP_DATA_PATH"])
        self.layout.addRow(QLabel("Temporary Data Path:"), self.temporaryPathLineEdit)

        self.featureGroupLayout = QHBoxLayout()
        self.vmCheckbox = QCheckBox("VM Control")
        self.guacCheckbox = QCheckBox("Guacamole")
        self.proxmoxCheckbox = QCheckBox("Proxmox Pools")
        self.keycloakCheckbox = QCheckBox("Keycloak")
        self.rocketChatCheckbox = QCheckBox("RocketChat")
        self.ctfdCheckbox = QCheckBox("CTFd")
        self.featureGroupLayout.addWidget(self.vmCheckbox)
        self.featureGroupLayout.addWidget(self.guacCheckbox)
        self.featureGroupLayout.addWidget(self.proxmoxCheckbox)
        self.featureGroupLayout.addWidget(self.keycloakCheckbox)
        self.featureGroupLayout.addWidget(self.rocketChatCheckbox)
        self.featureGroupLayout.addWidget(self.ctfdCheckbox)
        if self.s.getConfig()["FEATURES"]["VM"] == "True":
            self.vmCheckbox.setChecked(True)
        else:
            self.vmCheckbox.setChecked(False)
        if self.s.getConfig()["FEATURES"]["GUAC"] == "True":
            self.guacCheckbox.setChecked(True)
        else:
            self.guacCheckbox.setChecked(False)
        if self.s.getConfig()["FEATURES"]["PROXMOX"] == "True":
            self.proxmoxCheckbox.setChecked(True)
        else:
            self.proxmoxCheckbox.setChecked(False)
        if self.s.getConfig()["FEATURES"]["KEYCLOAK"] == "True":
            self.keycloakCheckbox.setChecked(True)
        else:
            self.keycloakCheckbox.setChecked(False)
        if self.s.getConfig()["FEATURES"]["ROCKETCHAT"] == "True":
            self.rocketChatCheckbox.setChecked(True)
        else:
            self.rocketChatCheckbox.setChecked(False)
        if self.s.getConfig()["FEATURES"]["CTFD"] == "True":
            self.ctfdCheckbox.setChecked(True)
        else:
            self.ctfdCheckbox.setChecked(False)

        self.layout.addRow(QLabel("Enable Features"), self.featureGroupLayout)

        self.groupLayout = QHBoxLayout()
        self.vboxRadio = QRadioButton("VirtualBox")
        self.vmwareRadio = QRadioButton("VMware Workstation")
        self.proxmoxRadio = QRadioButton("Proxmox")
        self.buttonGroup = QButtonGroup()
        self.buttonGroup.addButton(self.vboxRadio)
        self.buttonGroup.addButton(self.vmwareRadio)
        self.buttonGroup.addButton(self.proxmoxRadio)
        self.groupLayout.addWidget(self.vboxRadio)
        self.groupLayout.addWidget(self.vmwareRadio)
        self.groupLayout.addWidget(self.proxmoxRadio)
        if self.s.getConfig()["HYPERVISOR"]["ACTIVE"] == "VBOX":
            self.vboxRadio.setChecked(True)
        elif self.s.getConfig()["HYPERVISOR"]["ACTIVE"] == "VMWARE":
            self.vmwareRadio.setChecked(True)
        elif self.s.getConfig()["HYPERVISOR"]["ACTIVE"] == "PROXMOX":
            self.proxmoxRadio.setChecked(True)
        else:
            self.vmwareRadio.setChecked(True)
        self.layout.addRow(QLabel("Active Hypervisor"), self.groupLayout)

        self.formGroupBox.setLayout(self.layout)

    def exec_(self):
        logging.debug("ConfigurationDialog(): exec_() instantiated")
        result = super(ConfigurationDialog, self).exec_()
        if str(result) == str(1):
            logging.debug("dialog_response(): OK was pressed")
            # For each value on the form, write it to the config file
            self.s.writeConfig("VBOX", "VBOX_PATH", self.virtualboxPathLineEdit.text())
            self.s.writeConfig("VBOX", "VMANAGE_PATH", self.vmanagePathLineEdit.text())
            
            self.s.writeConfig("VMWARE", "VMWARE_PATH", self.vmwarePathLineEdit.text())
            self.s.writeConfig("VMWARE", "VMANAGE_VM_PATH", self.vmwareVMPathLineEdit.text())
            self.s.writeConfig("VMWARE", "VMANAGE_CLI_PATH", self.vmwareCliPathLineEdit.text())
            self.s.writeConfig("VMWARE", "VMANAGE_RUN_PATH", self.vmwareRunPathLineEdit.text())
            self.s.writeConfig("VMWARE", "VMANAGE_OVF_PATH", self.vmwareOVFPathLineEdit.text())
            self.s.writeConfig("VMWARE", "VMWARE_PREFSFILE_PATH", self.vmwarePrefsPathLineEdit.text())
            self.s.writeConfig("VMWARE", "VMWARE_INVENTORYFILE_PATH", self.vmwareInvPathLineEdit.text())

            self.s.writeConfig("PROXMOX", "VMANAGE_VMCONF_PATH", self.proxmoxVMPathLineEdit.text())
            self.s.writeConfig("PROXMOX", "VMANAGE_QM_PATH", self.proxmoxQMPathLineEdit.text())
            self.s.writeConfig("PROXMOX", "VMANAGE_PVESH_PATH", self.proxmoxPVESHPathLineEdit.text())
            self.s.writeConfig("PROXMOX", "VMANAGE_QMRESTORE_PATH", self.proxmoxQMRestorePathLineEdit.text())
            self.s.writeConfig("PROXMOX", "VMANAGE_STORAGE_VOL", self.proxmoxStorageVolLineEdit.text())
            self.s.writeConfig("PROXMOX", "VMANAGE_NODE_NAME", self.proxmoxNodeNameLineEdit.text())
            self.s.writeConfig("PROXMOX", "VMANAGE_SERVER", self.proxmoxServerLineEdit.text())
            self.s.writeConfig("PROXMOX", "VMANAGE_APIPORT", self.proxmoxApiPortLineEdit.text())
            self.s.writeConfig("PROXMOX", "VMANAGE_CMDPORT", self.proxmoxCmdPortLineEdit.text())
            self.s.writeConfig("PROXMOX", "VMANAGE_MAXCREATEJOBS", self.proxmoxMaxCreateJobsLineEdit.text())
            self.s.writeConfig("PROXMOX", "VMANAGE_SNAPWAITTIME", self.proxmoxSnapWaitTimeLineEdit.text())

            self.s.writeConfig("BROWSER", "BROWSER_PATH", self.browserPathLineEdit.text())
            
            self.s.writeConfig("EXPERIMENTS", "EXPERIMENTS_PATH", self.experimentPathLineEdit.text())
            self.s.writeConfig("EXPERIMENTS", "TEMP_DATA_PATH", self.temporaryPathLineEdit.text())

            self.s.writeConfig("FEATURES", "VM", str(self.vmCheckbox.isChecked()))
            self.s.writeConfig("FEATURES", "GUAC", str(self.guacCheckbox.isChecked()))
            self.s.writeConfig("FEATURES", "PROXMOX", str(self.proxmoxCheckbox.isChecked()))
            self.s.writeConfig("FEATURES", "KEYCLOAK", str(self.keycloakCheckbox.isChecked()))
            self.s.writeConfig("FEATURES", "ROCKETCHAT", str(self.rocketChatCheckbox.isChecked()))
            self.s.writeConfig("FEATURES", "CTFD", str(self.ctfdCheckbox.isChecked()))

            if self.vboxRadio.isChecked():
                self.s.writeConfig("HYPERVISOR", "ACTIVE", "VBOX")
            elif self.vmwareRadio.isChecked():
                self.s.writeConfig("HYPERVISOR", "ACTIVE", "VMWARE")
            elif self.proxmoxRadio.isChecked():
                self.s.writeConfig("HYPERVISOR", "ACTIVE", "PROXMOX")

            return (QMessageBox.Ok)
        return (QMessageBox.Cancel)
        