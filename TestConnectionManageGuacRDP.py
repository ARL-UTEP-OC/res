import logging
import sys, traceback
import threading
import json
import os
from engine.Manager.ConnectionManage.ConnectionManage import ConnectionManage
from engine.ExternalIFX.GuacIFX import GuacIFX
from engine.Configuration.ExperimentConfigIO import ExperimentConfigIO
from engine.Manager.ConnectionManage.ConnectionManageGuacRDP import ConnectionManageGuacRDP
import time

if __name__ == "__main__":
    logging.getLogger().setLevel(logging.DEBUG)
    logging.debug("Starting Program")

    logging.debug("Instantiating ConnectionManageGuacRDP")

    c = ConnectionManageGuacRDP()
    creds_file=os.path.join("utils","guac","default_users.csv")

    logging.info("Creating connection")
    c.createConnections("sample", "192.168.22.101:32769", "guacadmin", "guacadmin", "/guacamole", "http", maxConnections="1", maxConnectionsPerUser="1", width="1400", height="1050", bitdepth="16", creds_file=creds_file, itype="set", name="all")
    logging.info("Complete")
    time.sleep(10)
    logging.info("Getting status")
    res = c.getConnectionManageStatusAll("192.168.22.10:32768", "guacadmin", "guacadmin", "/guacamole", "http")
    logging.info("Status:" + str(res))
    logging.info("Complete")
    time.sleep(10)
    logging.info("Removing connection")
    c.removeConnections("sample", "192.168.22.101:32769", "guacadmin", "guacadmin", "/guacamole", "http", creds_file=creds_file)

    logging.info("Creating set 1 connection")
    c.createConnections("sample", "192.168.22.101:32769", "guacadmin", "guacadmin", "/guacamole", "http", maxConnections="1", maxConnectionsPerUser="1", width="1400", height="1050", bitdepth="16", creds_file=creds_file, itype="set", name="2")
    time.sleep(10)
    logging.info("Clearing all entries")
    c.clearAllConnections("192.168.22.101:32769", "guacadmin", "guacadmin", "/guacamole", "http")

    logging.info("Operation Complete")