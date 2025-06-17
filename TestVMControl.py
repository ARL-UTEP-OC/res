import logging
import sys, traceback
import threading
import os
import csv
import time
import datetime
from engine.Manager.ConnectionManage.ConnectionManage import ConnectionManage
from engine.Manager.ConnectionManage.ConnectionManageRESVMControl import ConnectionManageRESVMControl
import paramiko
from engine.Configuration.ExperimentConfigIO import ExperimentConfigIO
from engine.Configuration.SystemConfigIO import SystemConfigIO
from engine.Configuration.UserPool import UserPool
from threading import RLock

if __name__ == "__main__":
    logging.getLogger().setLevel(logging.DEBUG)
    logging.debug("Starting Program")

    logging.debug("Instantiating Engine")
    rvc = ConnectionManageRESVMControl()
    rvc.getVMControlSSH("test", username, password)
    rvc.executeSSH("source ~/miniconda3/etc/profile.d/conda.sh && conda activate res && nohup pyro5-ns &")

