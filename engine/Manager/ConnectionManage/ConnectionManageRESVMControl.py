import logging
import sys, traceback
import threading
import os
import csv
import time
import datetime
from engine.Manager.ConnectionManage.ConnectionManage import ConnectionManage
import paramiko
from engine.Configuration.ExperimentConfigIO import ExperimentConfigIO
from engine.Configuration.SystemConfigIO import SystemConfigIO
from engine.Configuration.UserPool import UserPool
from threading import RLock

class ConnectionManageRESVMControl(ConnectionManage):
#
    def __init__(self):
        logging.debug("ConnectionManageRESVMControl(): instantiated")
        ConnectionManage.__init__(self)
        self.vmcontrol = None
        self.eco = ExperimentConfigIO.getInstance()
        self.usersConnsStatus = {}
        self.lock = RLock()
        self.s = SystemConfigIO()
        self.sshusername = None
        self.sshpassword = None

    def getVMControlSSH(self, configname, username=None, password=None):
        logging.debug("getVMControlSSH(): instantiated")
        try:
            
            vmHostname, vmserversshport, rdisplayhostname, chatserver, challengesserver, vmcontrolhostname, vmcontrolsshport, users_file = self.eco.getExperimentServerInfo(configname)
            server = vmcontrolhostname
            user = username
            splithostname = vmcontrolhostname.split("://")
            if len(splithostname) > 1:
                rsplit = splithostname[1]
                server = rsplit.split("/")[0]
                server = server.split(":")[0]
            
            if self.vmcontrol == None and user != None and password != None and user.strip() != "" and password.strip() != "":
                # Create SSH client
                self.vmcontrol = paramiko.SSHClient()
                self.vmcontrol.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                # Connect to the remote server
                logging.debug(f"getVMControlSSH(): Connecting to " + str(server) + ":" + str(vmcontrolsshport) + " as " + str(username))
                self.vmcontrol.connect(hostname=server, port=vmcontrolsshport, username=username, password=password)
                self.sshusername = user
                self.sshpassword = password
            elif self.vmcontrol != None and user != None and password != None and user.strip() != "" and password.strip() != "":
                self.vmcontrol = None
                # Create SSH client
                self.vmcontrol = paramiko.SSHClient()
                self.vmcontrol.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                # Connect to the remote server
                logging.debug(f"getVMControlSSH(): Connecting to " + str(server) + ":" + str(vmcontrolsshport) + " as " + str(username))
                self.vmcontrol.connect(hostname=server, port=vmcontrolsshport, username=username, password=password)
                self.sshusername = user
                self.sshpassword = password
            return self.vmcontrol
        except Exception:
            logging.error("Error in getVMControlSSH(): An error occured when trying to connect to remote service with ssh; possibly incorrect credentials.")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
            self.vmcontrol = None
            return None

    def executeSSH(self, command, sudo=True):
        logging.debug("executeSSH(): instantiated")
        feed_password = False
        if sudo and self.sshusername != "root":
            command = "sudo -S -p '' %s" % command
            feed_password = self.sshpassword is not None and len(self.sshpassword) > 0
        stdin, stdout, stderr = self.vmcontrol.exec_command(command)
        if feed_password:
            stdin.write(self.sshpassword + "\n")
            stdin.flush()
        return {'out': stdout.readlines(), 
                'err': stderr.readlines(),
                'retval': stdout.channel.recv_exit_status()}

    def startPyroService(self, configname, username=None, password=None):
        logging.debug("startPyroService(): instantiated")
        #get docker0 interface ip address
        #nohup pyro5-ns -n <docker0-ip> -p 10291
        try:
            vmcontrolssh = self.getVMControlSSH(configname=configname, username=username, password=password)
            if vmcontrolssh == None:
                return None
        except Exception:
            logging.error("Error in statusPyro(): An error occured when trying to connect to remote service")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
            return None

        #check if pyro service is already running
        if self.statusPyro(configname, username, password) == True:
            logging.warning("startVMControl(): Pyro5 nameservice already running, stop and restart to create new instance")
            logging.debug("Using existing pyro5-ns")
            return True
        else:
            #start pyro5-ns
            logging.debug("startVMControl(): Starting Pyro5 Nameservice")
            res = self.executeSSH("source ~/miniconda3/etc/profile.d/conda.sh && conda activate res && nohup pyro5-ns &", sudo=False)
            logging.debug("pyro5-ns started")
            return True
        return None

    def stopPyroService(self, configname, username=None, password=None):
        logging.debug("stopPyroService(): instantiated")
        #conda activate res
        try:
            vmcontrolssh = self.getVMControlSSH(configname=configname, username=username, password=password)
            if vmcontrolssh == None:
                return None
        except Exception:
            logging.error("Error in statusPyro(): An error occured when trying to connect to remote service")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
            return None

        try:
            if self.statusPyro(configname, username, password) == True:
                logging.debug("Attempting to stop pyro5-ns process")
                res = self.executeSSH("pkill pyro5-ns", sudo=False)
                logging.debug("Stopped pyro5-ns process")
                if self.statusPyro(configname, username, password) == True:
                    return False #could not be stopped
                return True #stopped succesfully
            else:
                logging.debug("Pyro service already not running")
                return False
        except Exception:
            logging.error("Error in runCreateConnections(): An error occured when trying to connect to remote service")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
            return False

    def statusPyro(self, configname, username=None, password=None):
        logging.debug("getPyroStatus(): instantiated")

        try:
            vmcontrolssh = self.getVMControlSSH(configname=configname, username=username, password=password)
            if vmcontrolssh == None:
                return None
        except Exception:
            logging.error("Error in statusPyro(): An error occured when trying to connect to remote service")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
            return None

        try:
            res = self.executeSSH("pgrep pyro5-ns", sudo=False)
            if len(res['out']) > 0:
                return True
            else:
                return False
        except Exception:
            logging.error("Error in runCreateConnections(): An error occured when trying to connect to proxmox")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
            return False

    def startVMControl(self, configname, username=None, password=None):
        logging.debug("startVMControl(): instantiated")

        try:
            vmcontrolssh = self.getVMControlSSH(configname=configname, username=username, password=password)
            if vmcontrolssh == None:
                return None
        except Exception:
            logging.error("Error in startVMControl(): An error occured when trying to connect to remote service")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
            return None
        self.startPyroService(configname, username, password)

        #copy creds file

        #copy configname configfile

        #stop and then start docker container

    def statusServiceRemote(self, configname, username=None, password=None):
        logging.debug("statusServiceRemote(): instantiated")    
        #conda activate res
        try:
            vmcontrolssh = self.getVMControlSSH(configname=configname, username=username, password=password)
            if vmcontrolssh == None:
                return None
        except Exception:
            logging.error("Error in statusServiceRemote(): An error occured when trying to connect to remote service")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
            return None

        try:
            res = self.executeSSH("docker ps --filter 'name=resvmcontrol'", sudo=True)
            if len(res['out']) > 1 and 'resvmcontrol' in ''.join(res['out']):
                return True
            else:
                if len(res['err']) > 0:
                    logging.error("Error in statusServiceRmote(): " + res['err'])
                return False
        except Exception:
            logging.error("Error in statusServiceRemote(): An error occured when trying to connect to remote service")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
            return False

    def startServiceRemote(self, configname, username=None, password=None):
        logging.debug("startServiceRemote(): instantiated")    
        try:
            vmcontrolssh = self.getVMControlSSH(configname=configname, username=username, password=password)
            if vmcontrolssh == None:
                return None
        except Exception:
            logging.error("Error in statusPyro(): An error occured when trying to connect to remote service")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
            return None

        #check if pyro service is already running
        if self.statusServiceRemote(configname, username, password) == True:
            logging.warning("startVMControl(): Docker service container already running, stop and restart to create new instance")
            logging.debug("Using existing service container")
            return True
        else:
            #start docker service
            logging.debug("startVMControl(): Starting Docker service container")
            res = self.executeSSH("docker start resvmcontrol", sudo=True)
            logging.debug("Docker container started")
            return True
    
    def stopServiceRemote(self, configname, username=None, password=None):
        logging.debug("stopServiceRemote(): instantiated")    
        try:
            vmcontrolssh = self.getVMControlSSH(configname=configname, username=username, password=password)
            if vmcontrolssh == None:
                return None
        except Exception:
            logging.error("Error in stopServiceRemote(): An error occured when trying to stop remote container")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
            return None

        #check if docker service is running
        if self.statusServiceRemote(configname, username, password) == True:
            logging.debug("stopServiceRemote(): Stopping Docker service container")
            res = self.executeSSH("docker stop resvmcontrol", sudo=True)
            logging.debug("Docker container stopped")
            return True
        else:
            #stop docker container
            logging.warning("stopVMControl(): docker container already stopped")
            return True

    def mkdirP(self, sftp, remote_directory):
        logging.debug("mkdirP(): instantiated")

        if remote_directory == '/':
            # absolute path so change directory to root
            sftp.chdir('/')
            return
        if remote_directory == '':
            # top-level relative directory must exist
            return
        try:
            sftp.chdir(remote_directory) # sub-directory exists
        except IOError:
            dirname, basename = os.path.split(remote_directory.rstrip('/'))
            self.mkdirP(sftp, dirname) # make parent directories
            sftp.mkdir(basename) # sub-directory missing, so created it
            sftp.chdir(basename)
            return True

    def statusCreds(self, configname, username=None, password=None):
        logging.debug("updateCredsRemote(): instantiated")
        #scp the creds_file to the remote host

    def updateConfig(self, configname, username=None, password=None):
        logging.debug("updateConfigRemote(): instantiated")
        #scp the config to the remote host

    def updateCreds(self, configname, username=None, password=None):
        logging.debug("statusCreds(): instantiated")
        #check if creds file exists on remote end
        try:
            vmcontrolssh = self.getVMControlSSH(configname=configname, username=username, password=password)
            if vmcontrolssh == None:
                return None
        except Exception:
            logging.error("Error in statusServiceRemote(): An error occured when trying to connect to remote service")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
            return None

        try:
            local_path = os.path.join(configname,"ExperimentData",configname,"Materials","creds.csv")
            remote_path = "/home/dockerutils/git/res/"
            os.path.join(remote_path,"ExperimentData",configname,"Materials","creds.csv")
            sftp_client = vmcontrolssh.open_sftp()

            # Extract the remote directory path from the full remote path
            remote_dir = os.path.dirname(remote_path)

            # Check if the remote directory exists and create it if not
            try:
                sftp_client.stat(remote_dir)  # Try to stat the directory
            except IOError:
                # Directory does not exist, so create it recursively
                self.mkdirP(sftp_client, remote_dir)
                logging.debug("Remote directory " + str(remote_dir) + " created.")

            # Upload the file
            sftp_client.put(local_path, remote_path)

        except Exception:
            logging.error("Error in statusServiceRemote(): An error occured when trying to connect to remote service")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
            return False

    def statusConfig(self, configname, username=None, password=None):
        logging.debug("credsExistsRemote(): instantiated")
        #check if config file exists on remote end