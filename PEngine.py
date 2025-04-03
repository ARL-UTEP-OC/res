from engine.Engine import Engine
from engine.Manager.ExperimentManage.ExperimentManage import ExperimentManage
from engine.Configuration.UserPool import UserPool
import Pyro5.api
import sys

if len(sys.argv) != 3:
    print("usage: PEngine.py Host-IP Host-Port")
    exit(-1)

hostip = sys.argv[1]
hostport = sys.argv[2]
print("HOSTIP: " + str(hostip) + " HOSTPORT: " + str(hostport))
# make a Pyro daemon
daemon = Pyro5.server.Daemon(host=hostip)
# find the name server
ns = Pyro5.api.locate_ns(host=hostip, port=int(hostport))

pyroEngine = Pyro5.server.expose(Engine)
# register the greeting maker as a Pyro object
uri = daemon.register(pyroEngine)   
# register the object with a name in the name server
ns.register("engine", uri)   

pyroUserPool = Pyro5.server.expose(UserPool)
# register the greeting maker as a Pyro object
uri = daemon.register(pyroUserPool)   
# register the object with a name in the name server
ns.register("userpool", uri)   

pyroExperimentManage = Pyro5.server.expose(ExperimentManage)
# register the greeting maker as a Pyro object
uri = daemon.register(pyroExperimentManage)   
# register the object with a name in the name server
ns.register("experimentmanage", uri)   

print("Ready.")
# start the event loop of the server to wait for calls
daemon.requestLoop()                   
