import logging
import sys, traceback
import threading
import os
import csv
from plugins.ctfi2.api import API
from engine.Manager.ChallengesManage.ChallengesManage import ChallengesManage
from engine.Configuration.ExperimentConfigIO import ExperimentConfigIO
from engine.Configuration.UserPool import UserPool
from guacapy import Guacamole
from threading import RLock

class ChallengesManageCTFd(ChallengesManage):
    def __init__(self):
        logging.debug("ChallengesManageGuacRDP(): instantiated")
        ChallengesManage.__init__(self)
        self.eco = ExperimentConfigIO.getInstance()
        self.challengeUsersStatus = {}
        self.challengesStats = {}
        self.lock = RLock()

    def create_user(self, api_session, username, password, email="", email_ext="@fake.com", type="user", verified="false", hidden="false", banned="false", fields=[]):
        logging.debug("create_user(): instantiated")
        if email == "":
            email = username+str(email_ext)
        logging.debug("create_user(): Adding User: " + str(username))
        result = api_session.user_add(name=username, password=password, email=email, type=type, verified=verified, hidden=hidden, banned=banned, fields=fields)
        if result != {}:
            return True
        return False

    def create_users(self, api_session, users_passes, ignore=[""]):
        logging.debug("create_users(): instantiated")
        results = []
        if isinstance(ignore, str):
            ignore = [ignore]
        for (user, password) in users_passes:
            name = user
            if name.lower() not in (string.lower() for string in ignore):
                logging.debug("create_user(): Adding User: " + str(name))
                results.append((user, self.create_user(api_session, user, password)))
        return results
    
    def remove_user(self, api_session, userid):
        logging.debug("remove_user(): instantiated")
        result = api_session.user_delete(id=userid)
        return result

    def remove_users(self, api_session):
        logging.debug("remove_users(): instantiated")
        results = []
        users = api_session.users_get()
        users_dict = {}

        return results

    def get_teams_members(self, api_session):
        logging.debug("get_teams_members(): instantiated")
        users = api_session.users_get()
        users_dict = {}
        logging.debug("Num Users: " + str(len(users)))
        for user in users:
            logging.debug("USER: " + str(user.get("name")) + " " + str(user.get("id")) )
            users_dict[user.get("id")] = user.get("name")

        teams_info = api_session.teams_get()
        teams_members_list = []
        logging.debug("Num Teams: " + str(len(teams_info)))
        #teams_info: [{'country': None, 'created': '2021-04-01T22:45:49+00:00', 'website': None, 'hidden': False, 'affiliation': None, 'banned': False, 'secret': None, 'oauth_id': None, 'captain_id': 46, 'email': None, 'bracket': None, 'name': 'team5', 'fields': [], 'id': 12}, {'country': None, 'created': '2021-04-01T22:46:23+00:00', 'website': None, 'hidden': False, 'affiliation': None, 'banned': False, 'secret': None, 'oauth_id': None, 'captain_id': 40, 'email': None, 'bracket': None, 'name': 'team6', 'fields': [], 'id': 13}, {'country': None, 'created': '2021-04-01T22:47:10+00:00', 'website': None, 'hidden': False, 'affiliation': None, 'banned': False, 'secret': None, 'oauth_id': None, 'captain_id': 33, 'email': None, 'bracket': None, 'name': 'chompers', 'fields': [], 'id': 14}, {'country': None, 'created': '2021-04-01T22:47:22+00:00', 'website': None, 'hidden': False, 'affiliation': None, 'banned': False, 'secret': None, 'oauth_id': None, 'captain_id': 34, 'email': None, 'bracket': None, 'name': 'BaconTeam', 'fields': [], 'id': 15}, {'country': None, 'created': '2021-04-01T22:47:38+00:00', 'website': None, 'hidden': False, 'affiliation': None, 'banned': False, 'secret': None, 'oauth_id': None, 'captain_id': 42, 'email': None, 'bracket': None, 'name': 'team2', 'fields': [], 'id': 16}, {'country': None, 'created': '2021-04-01T22:48:06+00:00', 'website': None, 'hidden': False, 'affiliation': None, 'banned': False, 'secret': None, 'oauth_id': None, 'captain_id': 44, 'email': None, 'bracket': None, 'name': 'Team 1', 'fields': [], 'id': 17}]
        for team_info in teams_info:
            #team_info: {'country': None, 'created': '2021-04-01T22:45:49+00:00', 'website': None, 'hidden': False, 'affiliation': None, 'banned': False, 'secret': None, 'oauth_id': None, 'captain_id': 46, 'email': None, 'bracket': None, 'name': 'team5', 'fields': [], 'id': 12}
            #print("TEAM: " + str(team_info.get("name")) + " ID: " + str(team_info.get("id")) )
            team_name = team_info.get("name")
            team_id = team_info.get("id")
            #team_all_info: [{'country': None, 'created': '2021-04-01T22:45:49+00:00', 'website': None, 'affiliation': None, 'banned': False, 'email': None, 'name': 'team5', 'fields': [], 'id': 12, 'members': [31, 46, 49], 'secret': None, 'oauth_id': None, 'bracket': None, 'hidden': False, 'captain_id': 46, 'place': '6th', 'score': 31}]
            team_all_info = api_session.team_get(team_info.get("id"))[0]
            #team_members: [1, 2, 3]
            team_members = team_all_info.get("members")
            #print("TEAM Members: " + str(team_members))
            #now get team name:
            team_members_list = [team_name]
            for member in team_members:
                #now add members by name
                #member: 31
                #print("MEMBER: " + str(member))
                if member not in users_dict:
                    continue
                team_members_list.append(users_dict[member])
                #print("TEAM MEMBERS LIST: " + str(team_members_list))
            teams_members_list.append(team_members_list)
        return teams_members_list

    #abstractmethod
    def createChallengesUsers(self, configname, ctfdHostname, username, password, creds_file="", itype="", name=""):
        logging.debug("createChallengesUsers(): instantiated")
        t = threading.Thread(target=self.runCreateChallengesUsers, args=(configname, ctfdHostname, username, password, creds_file, itype, name))
        t.start()
        t.join()
        return 0

    def runCreateChallengesUsers(self, configname, ctfdHostname, musername, mpassword, creds_file, itype, name):
        logging.debug("runCreateChallengesUsers(): instantiated")
        #call ctfd backend API to make challenges as specified in config file and then set the complete status
        rolledoutjson = self.eco.getExperimentVMRolledOut(configname)
        validchallengesnames = self.eco.getValidVMsFromTypeName(configname, itype, name, rolledoutjson)

        userpool = UserPool()
        usersConns = userpool.generateUsersConns(configname, creds_file=creds_file)

        try:

            api_session = API(prefix_url=ctfdHostname)
            api_session.login(musername,mpassword)

            if api_session == None:
                logging.error("runCreateChallengesUsers(): Error with ctfd challenges... skipping: " + str(ctfdHostname) + " " + str(musername))
    
                return -1
            users = []
            user_dict = api_session.users_get()
            for item in user_dict:
                users.append(item['name'])
            created_users = []
            try:
                for (username, password) in usersConns:
                    for challenge in usersConns[(username, password)]:
                        cloneVMName = challenge[0]
                        vmServerIP = challenge[1]
                        vrdpPort = challenge[2]
                        #only if this is a specific challenges to create; based on itype and name
                        if cloneVMName in validchallengesnames:
                            #if user doesn't exist, create it
                            if username not in users and username not in created_users:
                                logging.debug( "Creating User: " + username)
                                try:
                                    logging.info("runCreateChallengesUsers(): Adding User: " + str(username))
                                    result = self.create_user(api_session, username, password)
                                    if result == False:
                                        logging.error("runCreateChallengesUsers(): Could not add user: " + username + " may already exist; skipping...")
                                    else:
                                        created_users.append(username)
                                except Exception:
                                    logging.error("runCreateChallengesUsers(): Error in runCreateChallengesUsers(): when trying to add user.")
                                    exc_type, exc_value, exc_traceback = sys.exc_info()
                                    traceback.print_exception(exc_type, exc_value, exc_traceback)
            except Exception:
                    logging.error("runCreateChallengesUsers(): Error in runCreateChallengesUsers(): when trying to add challenge users.")
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    traceback.print_exception(exc_type, exc_value, exc_traceback)
            logging.debug("runCreateChallengesUsers(): Complete...")

        except Exception:
            logging.error("runCreateChallengesUsers(): Error in runCreateChallengesUsers(): An error occured ")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
        finally:
            self.writeStatus-=1

    #abstractmethod
    def clearAllChallengesUsers(self, ctfdHostname, username, password):
        logging.debug("clearAllChallengesUsers(): instantiated")
        self.writeStatus+=1
        t = threading.Thread(target=self.runClearAllChallengesUsers, args=(ctfdHostname, username, password))
        t.start()
        t.join()
        return 0

    def runClearAllChallengesUsers(self, ctfdHostname, username, password):
        try:
            
            api_session = API(prefix_url=ctfdHostname)
            api_session.login(username,password)
            if api_session == None:
                logging.error("runClearAllChallengesUsers(): Error with ctfd connection... quitting: " + str(ctfdHostname) + " " + str(username))
    
                return -1

            # Get list of all users
            user_dict = api_session.users_get()
            logging.info("runClearAllChallengesUsers(): Removing Num Users: " + str(len(user_dict)))
            for item in user_dict:
                username = item['name']
                id = item['id']
                logging.info( "Removing User: " + str(username) + " ID: " + str(id))
                try:
                    result = api_session.user_delete(id=id)
                    if result == False:
                        logging.warning("runClearAllChallengesUsers(): Could not remove user; perhaps user does not exist on system: " + str(username))
                except Exception:
                    logging.error("runClearAllChallengesUsers(): Error in runClearAllChallengesUsers(): when trying to remove user.")
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    #traceback.print_exception(exc_type, exc_value, exc_traceback)
        except Exception:
            logging.error("runCreateChallengesUsers(): Error in runCreateChallengesUsers(): An error occured ")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
        finally:
            self.writeStatus-=1

    #abstractmethod
    def removeChallengesUsers(self, configname, ctfdHostname, username, password, creds_file="", itype="", name=""):
        logging.debug("removeChallengesUsers(): instantiated")
        t = threading.Thread(target=self.runRemoveChallengesUsers, args=(configname,ctfdHostname, username, password, creds_file, itype, name))
        t.start()
        t.join()
        return 0

    def runRemoveChallengesUsers(self, configname, ctfdHostname, username, password, creds_file, itype, name):
        logging.debug("runRemoveChallengesUsers(): instantiated")
        #call ctfd backend API to make challenges as specified in config file and then set the complete status
        rolledoutjson = self.eco.getExperimentVMRolledOut(configname)
        validnames = self.eco.getValidVMsFromTypeName(configname, itype, name, rolledoutjson)
        userpool = UserPool()
        try:
            
            api_session = API(prefix_url=ctfdHostname)
            api_session.login(username,password)
            if api_session == None:
                logging.error("runRemoveChallengesConnections(): Error with ctfd connection... quitting: " + str(ctfdHostname) + " " + str(username))
    
                return -1
            user_dict = api_session.users_get()
            user_id = {}
            for item in user_dict:
                user_id[item['name']] = item['id']

            usersConns = userpool.generateUsersConns(configname, creds_file=creds_file)
            removed_users = []
            for (username, password) in usersConns:
                logging.debug( "Removing User: " + username)
                try:
                    for challenge in usersConns[(username, password)]:
                        cloneVMName = challenge[0]
                        if cloneVMName in validnames:
                            #don't try to remove the user if it doesn't exist or if it's already been removed
                            if username in user_id and user_id[username] != None and username not in removed_users:
                                logging.info("runRemoveChallengesConnections(): Removing User: " + str(username) + " ID: " + str(user_id[username]))
                                result = api_session.user_delete(id=user_id[username])
                                if result != True:
                                    logging.error("Could not remove user, perhaps the user doesn't exists; skipping... "+ str(username))
                                    user_id[username] = None
                                    removed_users.append(username)

                except Exception:
                        logging.error("runRemoveChallengesConnections(): Error in runRemoveChallengesConnections(): when trying to remove challenges.")
                        exc_type, exc_value, exc_traceback = sys.exc_info()
                        traceback.print_exception(exc_type, exc_value, exc_traceback)
            logging.debug("runRemoveChallengesConnections(): Complete...")
        except Exception:
            logging.error("runRemoveChallengesConnections(): Error in runRemoveChallengesConnections(): An error occured ")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_traceback)
        finally:
            self.writeStatus-=1

    #abstractmethod
    def openChallengeUsersStats(self, configname, experimentid, vmid):
        logging.debug("openChallengeUsersStats(): instantiated")
        self.writeStatus+=1
        t = threading.Thread(target=self.openChallengeUsersStats, args=(configname,))
        t.start()
        t.join()
        return 0

    def runOpenChallengeUsersStats(self, configname, experimentid, vmid):
        logging.debug("runOpenChallengeUsersStats(): instantiated")
        self.writeStatus-=1

    #abstractmethod
    def getChallengesManageStatus(self):
        logging.debug("getChallengesManageStatus(): instantiated")
        return {"readStatus" : self.readStatus, "writeStatus" : self.writeStatus, "usersChallengesStatus" : self.challengeUsersStatus, "challengesStats" : self.challengesStats}
    
    def getChallengesManageRefresh(self, ctfdHostname, username, password):
        logging.debug("getChallengesManageStatus(): instantiated")
        try:
            self.lock.acquire()
            self.challengeUsersStatus.clear()
            #get users, teams, scores
            
            api_session = API(prefix_url=ctfdHostname)
            api_session.login(username,password)
            if api_session == None:
                logging.error("runRemoveChallengesConnections(): Error with ctfd connection... quitting: " + str(ctfdHostname) + " " + str(username))
                return -1

            all_users_data = api_session.users_get()
            userids = []

            for item in all_users_data:
                userids.append(item['id'])
            for id in userids:
                indscore = "No Score"
                place = "No Place"
                user_data = api_session.user_get(int(id))
                if 'score' in user_data[0] and user_data[0]['score'] != None:
                    indscore = user_data[0]['score']
                if 'place' in user_data[0] and user_data[0]['place'] != None:
                    place = user_data[0]['place']

                team_id = "No Team"
                team_name = "No Team"
                team_score = "No Team"
                team_rank = "No Team"
                if 'team_id' in user_data[0] and user_data[0]['team_id'] != None:
                    team_data = api_session.team_get(int(user_data[0]['team_id']))
                    team_id = team_data[0]['id']
                    
                    if 'name' in team_data[0] and team_data[0]['name'] != None:
                        team_name = team_data[0]['name']
                    if 'score' in team_data[0] and team_data[0]['score'] != None:
                        team_score = team_data[0]['score']
                    if 'place' in team_data[0] and team_data[0]['place'] != None:
                        team_rank = team_data[0]['place']
                self.challengeUsersStatus[user_data[0]['name']] = (str(id),str(team_name)+":"+str(team_id),str(place),str(indscore),str(team_score),str(team_rank))
    
        except Exception as e:
            logging.error("Error in getChallengesManageStatus(). Could not refresh challenges or relation!")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            trace_back = traceback.extract_tb(exc_traceback)
            traceback.print_exception(exc_type, exc_value, exc_traceback)
        finally:
            self.lock.release()

    def getChallengesManageGetstats(self, ctfdHostname, username, password):
        logging.debug("getChallengesManageGetstats(): instantiated")
        try:
            self.lock.acquire()
            self.challengesStats.clear()
            #get users, teams, scores
            
            api_session = API(prefix_url=ctfdHostname)
            api_session.login(username,password)
            if api_session == None:
                logging.error("getChallengesManageGetstats(): Error with ctfd connection... quitting: " + str(ctfdHostname) + " " + str(username))
                return -1

            all_challenges_data = api_session.challenges_get()

            for challenge in all_challenges_data:
                id = str(challenge['id'])
                category = str(challenge['category'])
                name = str(challenge['name'])
                solves = str(challenge['solves'])
                value = str(challenge['value'])
                self.challengesStats[id] = (id,category,name,solves, value)
    
        except Exception as e:
            logging.error("Error in getChallengesManageStatus(). Could not refresh challenges or relation!")
            exc_type, exc_value, exc_traceback = sys.exc_info()
            trace_back = traceback.extract_tb(exc_traceback)
            traceback.print_exception(exc_type, exc_value, exc_traceback)
        finally:
            self.lock.release()

