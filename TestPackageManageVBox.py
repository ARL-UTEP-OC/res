import logging
import sys, traceback
import threading
import json
from engine.Manager.PackageManage.PackageManage import PackageManage
from engine.Manager.PackageManage.PackageManageVBox import PackageManageVBox
from engine.Manager.VMManage.VBoxManage import VBoxManage
from engine.Manager.VMManage.VBoxManageWin import VBoxManageWin
from engine.Manager.ExperimentManage.ExperimentManage import ExperimentManage
from engine.Configuration.SystemConfigIO import SystemConfigIO
import zipfile
import os
import time

if __name__ == "__main__":
    logging.getLogger().setLevel(logging.ERROR)
    logging.debug("Starting Program")

    resfilename = "samples\sample.res"

    logging.debug("Instantiating Experiment Config IO")
    vbm = VBoxManageWin()
    em = ExperimentManage()
    p = PackageManageVBox(vbm, em)
    logging.info("Importing file")
    p.importPackage(resfilename)

    logging.info("Exporting file")
    p.exportPackage("sample", "sample with space\export")

    logging.info("Operation Complete")