from gui.Helpers.KeycloakActions import ConnectionActions
from engine.Configuration.UserPool import UserPool
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QDateTime, Qt, QTimer, QThread, pyqtSignal, QObject
from engine.Configuration.ExperimentConfigIO import ExperimentConfigIO
from PyQt5.QtWidgets import (QApplication, QCheckBox, QComboBox, QDateTimeEdit,
        QDial, QDialog, QDialogButtonBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
        QProgressBar, QPushButton, QRadioButton, QScrollBar, QSizePolicy,
        QSlider, QSpinBox, QStyleFactory, QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView, QTableView, QTabWidget, QTextEdit,
        QVBoxLayout, QWidget, QMessageBox)

import logging

class KeycloakStatusWidget(QtWidgets.QWidget):
    def __init__(self, parent=None, configname=None, widgetname="", rolledoutjson=None, interest_vmnames = [], vmuser_mapping={}, status_bar=None):
        logging.debug("KeycloakStatusWidget instantiated")
        if configname == None:
            logging.error("configname cannot be empty")
            return None
        QtWidgets.QWidget.__init__(self, parent=None)
        self.parent = parent
        self.statusBar = status_bar
        self.widgetname = widgetname
        self.configname = configname
        self.rolledoutjson = rolledoutjson
        self.eco = ExperimentConfigIO.getInstance()

        self.setWindowTitle("KeycloakStatusWidget")
        self.setObjectName("KeycloakStatusWidget")
        self.layoutWidget = QtWidgets.QWidget()
        self.layoutWidget.setObjectName("layoutWidget")
        self.outerVertBox = QtWidgets.QVBoxLayout()
        self.outerVertBox.setObjectName("outerVertBox")
        self.layoutWidget.setLayout(self.outerVertBox)

        self.connStatusTable = QtWidgets.QTableWidget(parent)
        self.connStatusTable.setObjectName("connStatusTable")
        self.connStatusTable.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.connStatusTable.setSelectionBehavior(QTableView.SelectRows)
        self.connStatusTable.setSelectionMode(QTableView.SingleSelection)
        
        self.connStatusTable.setRowCount(0)
        self.connStatusTable.setColumnCount(5)
        self.connStatusTable.setHorizontalHeaderLabels(("Connection Name", "Generated User", "Generated Pass", "User Status", "Last Recorded"))
        self.connStatusTable.horizontalHeader().setStretchLastSection(True)
        self.connStatusTable.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.connStatusTable.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.connStatusTable.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.connStatusTable.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.connStatusTable.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        
        # Context menus
        self.connStatusTable.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.connStatusTable.customContextMenuRequested.connect(self.showContextMenu)
        self.connsContextMenu = QtWidgets.QMenu()
        self.createKeycloak = self.connsContextMenu.addAction("Create Users")
        self.createKeycloak.triggered.connect(self.menuItemSelected)
        self.removeKeycloak = self.connsContextMenu.addAction("Remove Users")
        self.removeKeycloak.triggered.connect(self.menuItemSelected)
        self.clearKeycloak = self.connsContextMenu.addAction("Clear All Users on Server")
        self.clearKeycloak.triggered.connect(self.menuItemSelected)
        # self.openKeycloak = self.connsContextMenu.addAction("Open Connections")
        # self.openKeycloak.triggered.connect(self.menuItemSelected)

        self.connStatusTable.setSortingEnabled(True)
        self.outerVertBox.addWidget(self.connStatusTable)

        self.setLayout(self.outerVertBox)
        self.retranslateUi(rolledoutjson, interest_vmnames, vmuser_mapping)

    def retranslateUi(self, rolledoutjson, interest_vmnames, vmuser_mapping):
        logging.debug("KeycloakStatusWidget: retranslateUi(): instantiated")
        user_num = 1
        if rolledoutjson == None:
            return
        (template_vms, num_clones) = rolledoutjson
        for template_vm in template_vms:
            for cloned_vm in template_vms[template_vm]:
                if interest_vmnames == [] or cloned_vm["name"] in interest_vmnames:
                    rowPos = self.connStatusTable.rowCount()
                    self.connStatusTable.insertRow(rowPos)
                    vmName = str(cloned_vm["name"])
                    vmCell = QTableWidgetItem(vmName)
                    connStatusCell = QTableWidgetItem(str("refresh req."))
                    username = "vrdp disabled"
                    password = "vrdp disabled"
                    if vmuser_mapping != {} and vmName in vmuser_mapping:
                        if vmuser_mapping[vmName] == "userfile_not_found":
                            (username, password) = ("userfile_not_found"+str(user_num), "userfile_not_found"+str(user_num))
                            user_num+=1
                        else:
                            (username, password) = vmuser_mapping[vmName]
                    usernameCell = QTableWidgetItem(username)
                    passwordCell = QTableWidgetItem(password)
                    userStatusCell = QTableWidgetItem(str("refresh req."))
                    # statusCell.setFlags(Qt.ItemIsEnabled)
                    self.connStatusTable.setItem(rowPos, 0, vmCell)
                    self.connStatusTable.setItem(rowPos, 1, usernameCell)
                    self.connStatusTable.setItem(rowPos, 2, passwordCell)
                    self.connStatusTable.setItem(rowPos, 3, userStatusCell)
                    self.connStatusTable.setItem(rowPos, 4, connStatusCell)
                    self.connStatusTable.resizeColumnToContents(0)

    def showContextMenu(self, position):
        logging.debug("showContextMenu() instantiated")
        self.connsContextMenu.popup(self.connStatusTable.mapToGlobal(position))

    def menuItemSelected(self):
        logging.debug("menuItemSelected(): instantiated")
        connRow = self.connStatusTable.currentRow()
        if connRow == None:
            logging.error("menuItemSelected(): No Row is Selected.")
            return
        connName = self.connStatusTable.item(connRow,0).text()
        actionlabelname = self.sender().text()
        vmserverip, vmserversshport, rdpbroker, chatserver, challengesserver, keycloakserver, users_file = self.eco.getExperimentServerInfo(self.configname)
        ConnectionActions().connectionActionEvent(self.parent, self.configname, actionlabelname, vmserverip, users_file, "vm", connName)
        self.statusBar.showMessage("Executed " + str(actionlabelname) + " on " + self.configname)

    def updateConnStatus(self, usersConnsStatus):
        logging.debug("updateConnStatus(): instantiated")
        #format: [(username, connName): {"user_status": user_perm, "connStatus": active}]
        for cell in range(0,self.connStatusTable.rowCount()):
            tableConnName = self.connStatusTable.item(cell, 0).text()
            tableUserName = self.connStatusTable.item(cell, 1).text()
            userStatusCellItem = self.connStatusTable.item(cell, 3)
            connStatusCellItem = self.connStatusTable.item(cell, 4)
            userStatus = "not_found"
            connStatus = "not_found"
            if (tableUserName, tableConnName) in usersConnsStatus:
                if "user_status" in usersConnsStatus[(tableUserName, tableConnName)] and usersConnsStatus[(tableUserName, tableConnName)]["user_status"] != None:
                    userStatus = usersConnsStatus[(tableUserName, tableConnName)]["user_status"]
                if "connStatus" in usersConnsStatus[(tableUserName, tableConnName)] and usersConnsStatus[(tableUserName, tableConnName)]["connStatus"] != None:
                    connStatus = usersConnsStatus[(tableUserName, tableConnName)]["connStatus"]
            userStatusCellItem.setText(userStatus)
            connStatusCellItem.setText(connStatus)
        logging.debug("updateConnStatus(): completed")

if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    ui = KeycloakStatusWidget()
    ui.show()
    sys.exit(app.exec_())
