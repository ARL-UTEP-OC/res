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
    isRunning = rvc.statusPyro("test", "user", "pass")
    logging.info("Pyro Service Status: " + str(isRunning))

    logging.info("Starting Remote VM Control")
    res =  rvc.startVMControl("test")

    logging.info("Stop Remote VM Control")
    res =  rvc.stopPyroService("test")

    logging.info("Status Remote VM Control")
    res =  rvc.statusPyro("test")
    logging.info("Pyro Service is running: " + str(res))

    isRunning = rvc.statusServiceRemote("test", "user", "pass")
    logging.info("Status Docker Service:: " + str(isRunning))

    logging.info("Starting Docker Service")
    res =  rvc.startServiceRemote("test")

    logging.info("Stop Docker Service")
    res =  rvc.stopServiceRemote("test")

    logging.info("Status Docker Service:")
    res =  rvc.statusServiceRemote("test")
    logging.info("Docker Service is running: " + str(res))

    