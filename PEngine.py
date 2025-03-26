from engine.Engine import Engine
from engine.Manager.ExperimentManage.ExperimentManage import ExperimentManage
from engine.Configuration.UserPool import UserPool
import Pyro5.api
import sys

if len(sys) != 2:
    print("usage: PEngine.py Host-IP Host-Port")

hostip = sys.argv[0]
hostport = sys.argv[1]

daemon = Pyro5.server.Daemon(host=hostip)         # make a Pyro daemon
ns = Pyro5.api.locate_ns(host=hostip, port=hostport)             # find the name server

pyroEngine = Pyro5.server.expose(Engine)
uri = daemon.register(pyroEngine)   # register the greeting maker as a Pyro object
ns.register("engine", uri)   # register the object with a name in the name server

pyroUserPool = Pyro5.server.expose(UserPool)
uri = daemon.register(pyroUserPool)   # register the greeting maker as a Pyro object
ns.register("userpool", uri)   # register the object with a name in the name server

pyroExperimentManage = Pyro5.server.expose(ExperimentManage)
uri = daemon.register(pyroExperimentManage)   # register the greeting maker as a Pyro object
ns.register("experimentmanage", uri)   # register the object with a name in the name server

print("Ready.")
daemon.requestLoop()                   # start the event loop of the server to wait for calls