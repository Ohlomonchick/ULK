import requests
from slugify import slugify
import logging
import json
from .config import *
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


def pf_login(url, name, password):
    url2 = url + '/store/public/auth/login/login'
    header1 = {
        'Content-Type': 'application/json;charset=UTF-8'
    }
    session = requests.Session()
    r1 = session.get(url, headers=header1, verify=False)
    header2 = {
        'Content-Type': 'application/json;charset=UTF-8',
        'Cookie': f'_session={session.cookies.get_dict()["_session"]}',
    }
    payload2 = json.dumps(
        {
            'username': '' + name + '',
            'password': '' + password + '',
            'html': '0', 'captcha': ''
        }
    )
    r2 = requests.post(url2, headers=header2, data=payload2, verify=False)
    return r2.cookies, session.cookies.get_dict()["_session"]


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
                "user_workspace": urljoin(PNET_BASE_DIR, username),
                "note": "",
                "max_node": "",
                "max_node_lab": ""
            }
        ]
    }
    try:
        r = requests.post(
            url=url + '/store/public/admin/users/offAdd',
            json=user_params,
            cookies=cookie,
            verify=False
        )
        logger.debug("User {} created\npasswd: {}\nworkspace: {}\nServer response\t{}".format(username, password,
                                                                                              urljoin(PNET_BASE_DIR,
                                                                                                      username),
                                                                                              r.text))
    except Exception as e:
        logger.debug("Error with creating user\n{}\n".format(e))


def create_directory(url, path, dir_name, cookie):
    dir_name = slugify(dir_name)
    directory = {
        "path": path,
        "name": dir_name
    }
    r = requests.post(
        url + '/api/folders/add',
        json=directory,
        headers={'content-type': 'application/json'},
        cookies=cookie, verify=False
    )
    logger.debug(r.text)


def logout(url):
    header = {
        'content-type': 'application/json'
    }
    r = requests.get(url + '/api/auth/logout', headers=header, verify=False)
    logger.debug(r.text)


def create_lab(url, lab_name, lab_description, lab_path, cookie, xsrf, username):
    username = slugify(username)
    lab_parameters = {
        "author": username,
        "description": f"{lab_description}",
        "scripttimeout": 300,
        "countdown": 60,
        "version": 1,
        "name": f"{lab_name}",
        "body": "",
        "path": f"{lab_path}/{username}",
        "openable": 1,
        "openable_emails": ["1"],
        "joinable": 0,
        "joinable_emails": ["1"],
        "editable": 1,
        "editable_emails": ["1"]
    }

    try:
        r = requests.post(
            url + '/api/labs',
            json=lab_parameters,
            cookies=cookie,
            verify=False
        )
        logger.debug(
            "Lab created at path {}\nServer response\t{}".format(f"{lab_path}/{username}", r.json()["message"]))
        logger.debug(r.text)
    except Exception as e:
        logger.debug("Error with creating lab\n{}\n".format(e))


def filter_user(url, cookie, xsrf):
    header = {
        "Content-Type": "application/json;charset=UTF-8",
        "X-XSRF-TOKEN": xsrf
        # 'Cookie': xsrf
    }
    payload = json.dumps(
        {
            "data": {
                "page_number": 1,
                "page_quantity": 1000,
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
    r = requests.post(
        url + '/store/public/admin/users/filter',
        headers=header,
        data=payload,
        cookies=cookie,
        verify=False
    )
    return r


def change_user_password(url, cookie, xsrf, pnet_login, new_password):
    users = filter_user(url, cookie, xsrf).json()
    user_params = None
    for user in users["data"]["data_table"]:
        if user["username"] == pnet_login:
            user_params = user
    if user_params:
        header = {
            "Content-Type": "application/json;charset=UTF-8",
            "X-XSRF-TOKEN": xsrf
        }
        user_params["password"] = new_password

        payload = json.dumps({
            "data": {
                "data_key":
                    [{"pod": user_params["pod"]}],
                    "data_editor": user_params
                }
            }
        )
        r = requests.post(
            url + '/store/public/admin/users/offEdit',
            headers=header,
            data=payload,
            cookies=cookie,
            verify=False
        )
        return r

    return None


def get_sessions_count(url, cookie):
    r = requests.get(
        url + '/store/public/admin/lab_sessions/count',
        headers={'content-type': 'application/json'},
        cookies=cookie,
        verify=False
    )
    return r


def filter_session(url, cookie, xsrf, page_number=1, page_quantity=25):
    header = {
        "Content-Type": "application/json;charset=UTF-8",
        "X-XSRF-TOKEN": xsrf
        # 'Cookie': xsrf
    }
    payload = json.dumps(
        {
            "data": {
                "page_number": page_number,
                "page_quantity": page_quantity,
                "page_total": 0,
                "flag_filter_change": True,
                "flag_filter_logic": "and",
                "data_sort": {
                    "lab_session_id": "desc"
                },
                "data_filter": {}
            }
        }
    )
    r = requests.post(
        url + '/store/public/admin/lab_sessions/filter',
        headers=header,
        data=payload,
        cookies=cookie, verify=False
    )
    return r


def create_session(url, lab, cookie):
    lab = '{ "path": "' + lab + '.unl" }'
    r = requests.post(
        url + '/api/labs/session/factory/create',
        data=lab,
        headers={'content-type': 'application/json'},
        cookies=cookie, verify=False
    )
    logger.debug(r)


def join_session(url, lab_session_id, cookie):
    lab_session_id = '{"lab_session":"' + str(lab_session_id) + '"}'
    r = requests.post(
        url + '/api/labs/session/factory/join',
        data=lab_session_id,
        headers={'content-type': 'application/json'},
        cookies=cookie,
        verify=False
    )
    logger.debug(r)


def create_node(url, node_params, cookie, xsrf):
    try:
        r = requests.post(
            url + '/api/labs/session/nodes/add',
            json=node_params,
            cookies=cookie,
            verify=False
        )
        logger.debug(
            "Node {} has been created\nServer response\t{}".format(node_params["template"], r.json()["message"]))
    except Exception as e:
        r = "False"
        logger.debug("Error with creating node\n{}\n".format(e))


def create_p2p(url, p2p_params, cookie):
    try:
        r = requests.post(
            url + '/api/labs/session/networks/p2p',
            json=p2p_params,
            cookies=cookie,
            verify=False
        )
        logger.debug("P2P {} has been created \nServer response\t{}".format(p2p_params["name"], r.json()["message"]))
    except Exception as e:
        r = "False"
        logger.debug("Error with creating P2P\n{}\n".format(e))


def destroy_session(url, lab_session_id, cookie):
    lab_session_id = '{"lab_session":"' + str(lab_session_id) + '"}'
    r = requests.post(
        url + '/api/labs/session/factory/destroy',
        data=lab_session_id,
        headers={'content-type': 'application/json'},
        cookies=cookie, verify=False
    )
    logger.debug(r)


def create_network(url, net_params, cookie):
    try:
        r = requests.post(
            url + '/api/labs/session/networks/add',
            json=net_params,
            cookies=cookie,
            verify=False
        )
        logger.debug(
            "Network {} has been created \nServer response\t{}".format(net_params["name"], r.json()["message"]))
    except Exception as e:
        r = "False"
        logger.debug("Error with creating network\n{}\n".format(e))


def create_p2p_nat(url, p2p_params, cookie):
    try:
        r = requests.post(
            url + '/api/labs/session/interfaces/edit',
            json=p2p_params,
            cookies=cookie,
            verify=False
        )
        logger.debug(
            "P2P_NAT {} has been created\nServer response\t{}".format(p2p_params["node_id"], r.json()["message"]))
    except Exception as e:
        r = "False"
        logger.debug("Error with creating P2P_NAT\n{}\n".format(e))


def delete_lab(url, cookie, lab_path):
    try:
        path = '{"path":"' + str(lab_path) + '.unl"}'
        r = requests.delete(
            url + '/api/labs',
            data=path,
            cookies=cookie,
            verify=False
        )
    except Exception as e:
        r = "False"
        logger.debug("Error with deleting lab\n{}\n".format(e))

    return r


def create_all_lab_nodes_and_connectors(url, lab_object, lab_path, cookie, xsrf, username):
    lab_name = lab_object.slug
    username = slugify(username)
    lab_path += "/" + username

    lab_slash_name = "/" + lab_name
    lab = lab_path + lab_slash_name
    logger.debug(lab)

    create_session(url, lab, cookie)
    users = filter_user(url, cookie, xsrf).json()

    r = get_sessions_count(url, cookie).json()
    count_labs = r["data"]
    logger.debug(count_labs)

    response_json = filter_session(url, cookie, xsrf, 1, count_labs).json()
    session_list = []

    for item in response_json["data"]["data_table"]:
        if item["lab_session_path"] == lab + '.unl':
            username = ""
            for user in users["data"]["data_table"]:
                if user["pod"] == item["lab_session_pod"]:
                    username = user["username"]
            session = [
                item["lab_session_id"],
                username,
                item["lab_session_path"]
            ]
            session_list.append(session)

    logger.debug(session_list)

    sess_id = 0
    for session in session_list:
        if session[1] == 'pnet_scripts':
            sess_id = session[0]

    join_session(url, sess_id, cookie)

    for node in lab_object.NodesData:
        if node:
            create_node(url, node, cookie, xsrf)

    for network in lab_object.NetworksData:
        if network:
            create_network(url, network, cookie)

    for connector in lab_object.ConnectorsData:
        if connector:
            create_p2p(url, connector, cookie)

    for cloudConnector in lab_object.Connectors2CloudData:
        if cloudConnector:
            create_p2p_nat(url, cloudConnector, cookie)

    destroy_session(url, sess_id, cookie)


def delete_lab_with_session_destroy(url: object, lab_name: object, lab_path: object, cookie: object, xsrf: object, username: object) -> object:
    username = slugify(username)
    lab_path += "/" + username

    lab_slash_name = "/" + lab_name
    lab = lab_path + lab_slash_name
    logger.debug(lab)

    r = get_sessions_count(url, cookie).json()
    count_labs = r["data"]
    logger.debug(count_labs)

    response_json = filter_session(url, cookie, xsrf, 1, max(1, count_labs))

    if (
            response_json.status_code != 204 and
            response_json.headers["content-type"].strip().startswith("application/json")
    ):
        try:
            response_json = response_json.json()
        except ValueError:
            logger.error("Failed to parse json in delete_lab_with_session_destroy")

    for item in response_json["data"]["data_table"]:
        if item["lab_session_path"] == lab + '.unl':
            logger.debug(destroy_session(url, item["lab_session_id"], cookie))

    r = delete_lab(url, cookie, lab).json()
    logger.debug(r)
