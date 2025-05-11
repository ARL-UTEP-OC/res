from engine.Configuration.ExperimentConfigIO import ExperimentConfigIO
from keycloak import KeycloakAdmin
from keycloak import KeycloakOpenIDConnection
import time
import logging
import sys, traceback
import csv
import os

def get_connection(server_url, username, password, realm_name="master"):
    keycloak_connection = KeycloakAdmin(server_url=server_url,
                        username=username,
                        password=password,
                        realm_name=realm_name,
                        verify=True)
    return keycloak_connection

def create_user(api_session, username, password, email="", email_ext="@fake.com"):
# Add user

    if email == "":
        email = username+str(email_ext)
    print("Creating user: " + username)
    result = api_session.create_user({"email": email,
        "username": username,
        "enabled": True,
        "firstName": username,
        "lastName": username,
        "credentials": [{"value": password, "type": "password",}]},
        exist_ok=True)

    print("Result: " + str(result))
    if result != {}:
        return True
    return False

def create_users(api_session, users_passes, ignore=[""]):
    results = []
    if isinstance(ignore, str):
        ignore = [ignore]
    for (user, password) in users_passes:
        name = user
        if name.lower() not in (string.lower() for string in ignore):
            results.append((user, create_user(api_session, user, password)))
    return results

def delete_user(api_session, username):
    # ID from username
    print("Getting Username ID: " + username)
    result = api_session.get_user_id(username)
    if result == None:
        return False
    # Delete user
    print("Removing user: " + result)
    result = api_session.delete_user(result)
    print("Result: " + str(result))
    if result == {}:
        return True
    return False

def delete_users(api_session, users, ignore=[""]):
    results = []
    if isinstance(ignore, str):
        ignore = [ignore]
    for name in users:
        if name.lower() not in (string.lower() for string in ignore):
            results.append((name, delete_user(api_session, name)))
    return results

def get_user_pass_fromfile(filename):
    logging.debug("get_user_pass_fromfile(): instantiated")
    #not efficient at all, but it's a quick lazy way to do it:
    answer = []
    i = 0
    try:
        if os.path.exists(filename) == False:
            logging.debug("get_user_pass_fromfile(): Filename: " + filename + " does not exists; returning")
            return None
        with open(filename) as infile:
            reader = csv.reader(infile, delimiter=" ")
            for user, password in reader:
                i = i+1
                answer.append((user, password))
        return answer
    except Exception as e:
        logging.error("Error in get_user_pass_fromfile().")
        exc_type, exc_value, exc_traceback = sys.exc_info()
        trace_back = traceback.extract_tb(exc_traceback)
        #traceback.print_exception(exc_type, exc_value, exc_traceback)
        return None

def get_users_fromfile(filename):
    logging.debug("get_users_fromfile(): instantiated")
    #not efficient at all, but it's a quick lazy way to do it:
    answer = []
    i = 0
    try:
        if os.path.exists(filename) == False:
            logging.debug("get_users_fromfile(): Filename: " + filename + " does not exists; returning")
            return None
        with open(filename) as infile:
            reader = csv.reader(infile, delimiter=" ")
            for user, password in reader:
                i = i+1
                answer.append(user)
        return answer
    except Exception as e:
        logging.error("Error in get_users_fromfile().")
        exc_type, exc_value, exc_traceback = sys.exc_info()
        trace_back = traceback.extract_tb(exc_traceback)
        #traceback.print_exception(exc_type, exc_value, exc_traceback)
        return None
#URL, username, password, realm_name, client_id, verify
api_session = get_connection(sys.argv[1], sys.argv[2], sys.argv[3])

#print("calling get_users_fromfile()")
path = "myfile.txt"
users_passes = get_user_pass_fromfile(path)

#Add Users
print("ADDING USERS")
result = create_users(api_session, users_passes)
print("ADD USER RESULT: " + str(result))

time.sleep(5)

print("DELETING USERS")
result = delete_users(api_session, get_users_fromfile(path))
print("DELETE USER RESULT: " + str(result))