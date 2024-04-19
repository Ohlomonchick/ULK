import requests
from slugify import slugify
import logging
import json
from interface.eveNodesData import NodesData, ConnectorsData, NetworksData, Connectors2CloudData

def pf_login(url, name, password):
    url2 = url + '/store/public/auth/login/login'
    header1 = {
       'Content-Type': 'application/json;charset=UTF-8'
    }
    session = requests.Session()
    r1 = session.get(url, headers = header1, verify = False)
    header2 = {
        'Content-Type': 'application/json;charset=UTF-8',
        'Cookie': f'_session={session.cookies.get_dict()["_session"]}',
    }
    payload2 = json.dumps(
        {
            'username':''+name+'',
            'password':''+password+'',
            'html':'0','captcha':''
        }
    )
    r2 = requests.post(url2, headers = header2, data = payload2, verify = False)
    return(r2.cookies, session.cookies.get_dict()["_session"])

def create_user(url, username, password, user_role, cookie):
    username = slugify(username)
    user_params = {
        "data": [
            {
                "username": username,
                "password": password,
                "role": "1",
                "user_status": "1",
                "active_time": "",
                "expired_time": "",
                "user_workspace": f"/Practice work/Test_Labs/api_test_dir/{username}",
                "note": "",
                "max_node": "",
                "max_node_lab": ""
            }
        ]
    }
    try: 
        r = requests.post(
            url = url + '/store/public/admin/users/offAdd', 
            json = user_params, 
            cookies = cookie, 
            verify = False
        )
        logging.debug("User {} created\npasswd: {}\nworkspace: {}\nServer response\t{}".format(username, password, f"/Practice work/Test_Labs/api_test_dir/{username}", r.text))
        # logging.debug("User {} created\npasswd: {}\nworkspace: {}\nServer response\t".format(username, password, f"/Practice work/Test_Labs/api_test_dir/{username}"))
    except Exception as e:
        # logging.debug("Error with creating user\n{}\n".format(e))
        pass

def create_directory(url, path, dir_name, cookie):
    dir_name = slugify(dir_name)
    directory = {
        "path": path,
        "name": dir_name
    }
    r = requests.post( \
       url + '/api/folders/add', \
       json = directory, \
       headers = {'content-type': 'application/json'}, \
       cookies=cookie, verify=False \
    )
    logging.debug(r.text)


def logout(url):
    header = {
       'content-type': 'application/json'
    }
    r = requests.get(url + '/api/auth/logout', headers = header, verify = False)
    logging.debug(r.text)


def create_lab(url, lab_name, lab_description, lab_path, cookie, xsrf, username):
    username = slugify(username)
    lab_parameters = {
        "author":username,
        "description": f"{lab_description}",
        "scripttimeout":300,
        "countdown":60,
        "version":1,
        "name": f"{lab_name}",
        "body":"",
        "path": f"{lab_path}/{username}",
        "openable":1,
        "openable_emails":["1"],
        "joinable":0,
        "joinable_emails":["1"],
        "editable":1,
        "editable_emails":["1"]
    }

    try:
        r = requests.post ( \
            url + '/api/labs', \
            json = lab_parameters, \
            cookies = cookie, \
            verify = False \
        )
        logging.debug("Lab created at path {}\nServer response\t{}".format(r.json()))
    except Exception as e:
        logging.debug("Error with creating lab\n{}\n".format(e))

    logging.debug(r.text)


def filter_user(url, cookie, xsrf):
    header = {
       "Content-Type": "application/json;charset=UTF-8",
       "X-XSRF-TOKEN": xsrf
       #'Cookie': xsrf
    }
    payload = json.dumps(
        {
            "data": {
                "page_number": 1,
                "page_quantity": 25,
                "page_total": 0,
                "flag_filter_change": True,
                "flag_filter_logic": "and",
                "data_sort": {
                    "online_time": "desc"
                },
                "data_filter": {}
            }
        }
    )
    r = requests.post(  \
        url + '/store/public/admin/users/filter',   \
        headers = header,   \
        data = payload,     \
        cookies = cookie,   \
        verify = False      \
    )
    return r

def get_sessions_count(url, cookie):
    r = requests.get( \
        url + '/store/public/admin/lab_sessions/count', \
        headers = {'content-type': 'application/json'}, \
        cookies = cookie,    \
        verify=False \
    )
    return r


def filter_session(url, cookie, xsrf, page_number = 1, page_quantity = 25):
    header = {
        "Content-Type": "application/json;charset=UTF-8",
        "X-XSRF-TOKEN":xsrf
        #'Cookie': xsrf
    }
    payload = json.dumps( \
        {   \
            "data": {   \
                "page_number": page_number,    \
                "page_quantity": page_quantity, \
                "page_total": 0,     \
                "flag_filter_change": True,  \
                "flag_filter_logic": "and",  \
                "data_sort": {              \
                    "lab_session_id": "desc" \
                },  \
                "data_filter": {}   \
            }   \
        }   \
    )
    r = requests.post( \
       url + '/store/public/admin/lab_sessions/filter',  \
       headers = header, \
       data = payload, \
       cookies = cookie, verify = False \
    )
    return r


def create_session(url, Lab, cookie):
    Lab = '{ "path": "' + Lab + '.unl" }'
    r = requests.post( \
       url+'/api/labs/session/factory/create', \
       data = Lab, \
       headers = {'content-type': 'application/json'}, \
       cookies=cookie, verify=False \
    )
    logging.debug(r)


def join_session( url, lab_session_id, cookie ):
    lab_session_id = '{"lab_session":"' + str(lab_session_id) + '"}'
    r = requests.post( \
       url + '/api/labs/session/factory/join',  \
       data = lab_session_id,  \
       headers = {'content-type': 'application/json'},  \
       cookies = cookie, \
       verify = False \
    )
    logging.debug(r)


def create_node(url, node_params, cookie, xsrf):
    try:
        r = requests.post ( \
                url + '/api/labs/session/nodes/add', \
                json = node_params, \
                cookies = cookie, \
                verify = False \
        )
        logging.debug("Node {} has been created {}\nServer response\t{}".format(r))
    except Exception as e:
        r = "False"
        logging.debug("Error with creating node\n{}\n".format(e))


def create_p2p(url, p2p_params, cookie):
    try:
        r = requests.post ( \
                url + '/api/labs/session/networks/p2p', \
                json = p2p_params, \
                cookies = cookie, \
                verify = False \
        )
        logging.debug("Node {} has been created {}\nServer response\t{}".format(r))
    except Exception as e:
        r = "False"
        logging.debug("Error with creating node\n{}\n".format(e))

def destroy_session(url, lab_session_id, cookie):
    lab_session_id = '{"lab_session":"' + str(lab_session_id) + '"}'
    r = requests.post( \
       url + '/api/labs/session/factory/destroy',  \
       data = lab_session_id, \
       headers = {'content-type': 'application/json'}, \
       cookies = cookie, verify=False
    )
    logging.debug(r)

def create_network(url, net_params, cookie):
    try:
        r = requests.post ( \
                url + '/api/labs/session/networks/add', \
                json = net_params, \
                cookies = cookie, \
                verify = False \
        )
        logging.debug("Node {} has been created {}\nServer response\t{}".format(r))
    except Exception as e:
        r = "False"
        logging.debug("Error with creating node\n{}\n".format(e))

def create_p2p_nat(url, p2p_params, cookie):
    try:
        r = requests.post ( \
                url + '/api/labs/session/interfaces/edit', \
                json = p2p_params, \
                cookies = cookie, \
                verify = False \
        )
        logging.debug("Node {} has been created {}\nServer response\t{}".format(r))
    except Exception as e:
        r = "False"
        logging.debug("Error with creating node\n{}\n".format(e))


def create_all_lab_nodes_and_connectiors(url, lab_name, lab_path, cookie, xsrf, username):
    username = slugify(username)
    lab_path += "/" + username


    lab_slash_name = "/" + lab_name
    lab = lab_path + lab_slash_name
    logging.debug(lab)
    response = create_session(url, lab, cookie)

    users = filter_user(url, cookie, xsrf).json()

    r = get_sessions_count(url, cookie).json()
    count_labs = r["data"]
    logging.debug(count_labs)

    response_json = filter_session(url, cookie, xsrf, 1, count_labs)

    response_json = response_json.json()

    session_list = []

    for item in response_json["data"]["data_table"]:
        if item["lab_session_path"] == lab + '.unl': 
            username = ""
            for user in users["data"]["data_table"]:
                if user["pod"] == item["lab_session_pod"] :
                    username = user["username"]   
            session = [
                        item["lab_session_id"], 
                        username, 
                        item["lab_session_path"] 
                    ]
            session_list.append( session )

    logging.debug(session_list[0])

    for session in session_list:
        if session[1] == 'pnet_scripts':
            sess_id = session[0]

    
    join_session(url, sess_id, cookie)

    for node in NodesData[lab_name]:
        create_node(url, node, cookie, xsrf)

    for network in NetworksData[lab_name]:
        create_network(url, network, cookie)

    for connector in ConnectorsData[lab_name]:
        create_p2p(url, connector, cookie)

    for cloudConnector in Connectors2CloudData[lab_name]:
        create_p2p_nat(url, cloudConnector, cookie)

    destroy_session(url, sess_id, cookie)