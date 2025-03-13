from flask import Flask, request, jsonify, render_template
import logging
import shlex
import argparse
import sys
import time
from engine.Manager.ExperimentManage.ExperimentManageVBox import ExperimentManageVBox
from engine.Engine import Engine
from engine.Configuration.UserPool import UserPool


app = Flask(__name__)

# Route to serve the HTML page (client)
@app.route('/')
def index():
    return render_template('index.html')

# Route to run a command
@app.route('/run_command', methods=['POST', 'OPTIONS'])
def run_command():
    # Get the password and configname from the request
    data = request.json
    username = data.get('username')
    password = data.get('password')
    configname = data.get('configname')
    command = data.get('command')
    
    # Check if configname is provided
    if not configname:
        return jsonify({"error": "No Scenario Name Provided"}), 400

    try:
        # Call the start vm command
        userpool = UserPool()
        creds_file = ""
        usersConns = userpool.generateUsersConns(configname, creds_file=creds_file)
        if (username, password) in usersConns:
            conn = usersConns[(username, password)][0]
            cloneVMName = conn[0]
        else:
            return jsonify({"error": "Invalid username or password"}), 403
        
        #####---Start Experiment Test#####
        ##Note that any guestcontrol operations will require guest additions to be installed on the VM
        logging.info("Starting Experiment")
        e = Engine()
        cmds = []
        if command == "start":
            cmds.append("experiment start malwarecomms vm " + str(cloneVMName))
            for cmd in cmds:
                e.execute(cmd)
                res = e.execute("experiment status")
                logging.debug("Waiting for experiment start to complete...")
                while res["writeStatus"] != ExperimentManageVBox.EXPERIMENT_MANAGE_COMPLETE:
                    time.sleep(.1)
                    logging.debug("Waiting for experiment start to complete...")
                    res = e.execute("experiment status")
            output = "Completed"
            output += "\n" + str(res)

        elif command == "stop":
            cmds.append("experiment stop malwarecomms vm " + str(cloneVMName))
            for cmd in cmds:
                e.execute(cmd)
                res = e.execute("vm-manage mgrstatus")
                logging.debug("Waiting for experiment start to complete...")
                while res["writeStatus"] != ExperimentManageVBox.EXPERIMENT_MANAGE_COMPLETE:
                    time.sleep(.1)
                    logging.debug("Waiting for experiment start to complete...")
                    res = e.execute("experiment status")
            output = "Completed"
            output += "\n" + str(res)

        elif command == "status":
            cmds.append("vm-manage refresh " + str(cloneVMName))
            cmds.append("vm-manage vmstatus " + str(cloneVMName))
            for cmd in cmds:
                e.execute(cmd)
                res = e.execute("vm-manage mgrstatus")
                logging.debug("Waiting for experiment start to complete...")
                while res["writeStatus"] != ExperimentManageVBox.EXPERIMENT_MANAGE_COMPLETE:
                    time.sleep(.1)
                    logging.debug("Waiting for experiment start to complete...")
                    res = e.execute("vm-manage mgrstatus")
            output = "Completed"
            output += "\n" + str(res)
                    
        elif command == "restore":
            cmds.append("experiment restore malwarecomms vm " + str(cloneVMName))
            for cmd in cmds:
                e.execute(cmd)
                res = e.execute("experiment status")
                logging.debug("Waiting for experiment start to complete...")
                while res["writeStatus"] != ExperimentManageVBox.EXPERIMENT_MANAGE_COMPLETE:
                    time.sleep(.1)
                    logging.debug("Waiting for experiment start to complete...")
                    res = e.execute("experiment status")
            output = "Completed"
            output += "\n" + str(res)
        
        return jsonify({"output": output}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)

