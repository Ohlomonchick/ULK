import requests
from slugify import slugify
import logging
import json
from functools import wraps

from .config import *

logger = logging.getLogger(__name__)


class UnauthorizedException(Exception):
    """
    Исключение, выбрасываемое при получении 412 ответа от PNET.
    Указывает на необходимость повторного логина.
    """
    def __init__(self, response):
        self.response = response
        super().__init__(f"Unauthorized (412): {response.text if hasattr(response, 'text') else 'Session expired'}")


def retry_pnet_request(max_attempts=3):
    """
    Декоратор для повторных попыток HTTP запросов к PNET.
    Делает ретраи при не-200/не-300 ответах или таймаутах.
    
    Args:
        max_attempts: Количество попыток (по умолчанию 3)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            last_response = None
            # Используем wrapper.__name__ так как @wraps копирует метаданные из func
            # С fallback на func.__name__ и затем на 'unknown_function'
            func_name = getattr(wrapper, '__name__', getattr(func, '__name__', 'unknown_function'))
            
            for attempt in range(1, max_attempts + 1):
                try:
                    result = func(*args, **kwargs)
                    
                    # Если функция возвращает response объект, проверяем статус код
                    if isinstance(result, requests.Response):
                        status_code = result.status_code
                        if 200 <= status_code < 400:
                            return result
                        elif status_code == 412:
                            # 412 Unauthorized - не ретраим, выбрасываем специальное исключение
                            logger.warning(
                                f"Unauthorized (412) in {func_name}: Session expired, re-login required"
                            )
                            raise UnauthorizedException(result)
                        else:
                            # Неуспешный статус код - поднимаем исключение для ретрая
                            if attempt == max_attempts:
                                logger.error(
                                    f"Error in {func_name}: HTTP {status_code} response after {max_attempts} attempts"
                                )
                                return result
                            # Для ретрая поднимаем исключение
                            raise requests.exceptions.HTTPError(
                                f"HTTP {status_code} response", response=result
                            )
                    
                    # Если функция не возвращает response или возвращает что-то другое
                    return result
                    
                except UnauthorizedException:
                    # 412 Unauthorized - не ретраим, пробрасываем исключение дальше
                    raise
                    
                except requests.exceptions.Timeout as e:
                    last_exception = e
                    if attempt == max_attempts:
                        logger.error(
                            f"Error in {func_name}: Timeout after {max_attempts} attempts: {str(e)}",
                            exc_info=True
                        )
                        raise
                    continue
                    
                except requests.exceptions.RequestException as e:
                    last_exception = e
                    if attempt == max_attempts:
                        logger.error(
                            f"Error in {func_name}: Request exception after {max_attempts} attempts: {str(e)}",
                            exc_info=True
                        )
                        raise
                    continue
                    
                except Exception as e:
                    last_exception = e
                    if attempt == max_attempts:
                        logger.error(
                            f"Error in {func_name}: Exception after {max_attempts} attempts: {str(e)}",
                            exc_info=True
                        )
                        raise
                    continue
            
            # Если все попытки исчерпаны и мы дошли сюда (не должно быть), поднимаем последнее исключение
            if last_exception is not None:
                raise last_exception
            return last_response
                
        return wrapper
    return decorator


def get_user_workspace_relative_path():
    STUDENT_WORKSPACE = get_student_workspace()
    base_dir = get_pnet_base_dir()
    if STUDENT_WORKSPACE in base_dir:
        base_dir = base_dir.replace(STUDENT_WORKSPACE, '')
        base_dir = base_dir.replace('//', '/')
    return base_dir

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


def create_user(url, username, password, user_role='1', cookie=None):
    relative_path = get_user_workspace_relative_path()
    user_params = {
        "data": [
            {
                "username": username,
                "password": password,
                "role": user_role,
                "user_status": "1",
                "active_time": "",
                "expired_time": "",
                "user_workspace": f'{relative_path}/{username}',
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
        logger.debug("User {} created\npasswd: {}\nworkspace: {}\nServer response\t{}".format(
            username, password, f'{relative_path}/{username}', r.text)
        )
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
        "joinable": 1,
        "joinable_emails": ["1"],
        "editable": 0,
        "editable_emails": ["1"]
    }

    try:
        r = requests.post(
            url + '/api/labs',
            json=lab_parameters,
            cookies=cookie,
            verify=False,
            timeout=2  # 2 секунды таймаут для создания лабы
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
        verify=False,
        timeout=4  # 4 секунды таймаут для фильтрации пользователей
    )
    return r


def get_user_params(url, cookie, xsrf, pnet_login):
    users = filter_user(url, cookie, xsrf).json()
    user_params = None
    for user in users["data"]["data_table"]:
        if user["username"] == pnet_login:
            user_params = user
    return user_params


def change_user_params(url, cookie, xsrf, new_params):
    header = {
        "Content-Type": "application/json;charset=UTF-8",
        "X-XSRF-TOKEN": xsrf
    }
    payload = json.dumps({
        "data": {
            "data_key":
                [{"pod": new_params["pod"]}],
            "data_editor": new_params
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


def change_user_password(url, cookie, xsrf, pnet_login, new_password):
    user_params = get_user_params(url, cookie, xsrf, pnet_login)
    if user_params:
        user_params["password"] = new_password
        return change_user_params(url, cookie, xsrf, user_params)
    return None


def change_user_workspace(url, cookie, xsrf, pnet_login, new_workspace):
    user_params = get_user_params(url, cookie, xsrf, pnet_login)
    if user_params:
        user_params["user_workspace"] = new_workspace
        return change_user_params(url, cookie, xsrf, user_params)
    return None


def get_sessions_count(url, cookie):
    r = requests.get(
        url + '/store/public/admin/lab_sessions/count',
        headers={'content-type': 'application/json'},
        cookies=cookie,
        verify=False
    )
    return r


def get_auth_info(url, cookie):
    """Получает информацию о текущем пользователе через /api/auth"""
    r = requests.get(
        url + '/api/auth',
        headers={'content-type': 'application/json'},
        cookies=cookie,
        verify=False,
        timeout=4
    )
    return r


def filter_session(url, cookie, xsrf, page_number=1, page_quantity=25, path_contains=None):
    header = {
        "Content-Type": "application/json;charset=UTF-8",
        "X-XSRF-TOKEN": xsrf
        # 'Cookie': xsrf
    }
    
    # Формируем data_filter в зависимости от наличия path_contains
    data_filter = {}
    if path_contains:
        data_filter = {
            "lab_session_path": {
                "logic": "and",
                "data": [["contain", path_contains]]
            }
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
                "data_filter": data_filter
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
        cookies=cookie, verify=False,
        timeout=4  # 4 секунды таймаут для создания сессии
    )
    logger.debug(r)


def join_session(url, lab_session_id, cookie):
    lab_session_id = '{"lab_session":"' + str(lab_session_id) + '"}'
    r = requests.post(
        url + '/api/labs/session/factory/join',
        data=lab_session_id,
        headers={'content-type': 'application/json'},
        cookies=cookie,
        verify=False,
        timeout=4  # 4 секунды таймаут для подключения к сессии
    )
    logger.debug(r)
    logger.debug(r.json())
    return r


def get_session_id_by_filter(url, cookie, xsrf, lab_path):
    """
    Получает session_id по пути к лабе через filter_session.
    
    Args:
        url: URL PNET сервера
        cookie: Cookie для аутентификации
        xsrf: XSRF токен
        lab_path: Путь к лабе (например, /api_test_dir/komanda-a/lab.unl)
    
    Returns:
        tuple: (session_id, error_message) где session_id - ID сессии или None при ошибке
    """
    try:
        response = filter_session(
            url,
            cookie,
            xsrf,
            page_number=1,
            page_quantity=50,
            path_contains=lab_path
        )
        
        if response.status_code == 204:
            return None, "No sessions found"
        
        if response.status_code not in range(200, 400):
            return None, f"Failed to search sessions: {response.text}"
        
        if not response.headers.get("content-type", "").strip().startswith("application/json"):
            return None, "Invalid response from session search"
        
        data = response.json()
        target_path = lab_path if lab_path.endswith('.unl') else f"{lab_path}.unl"
        sessions = data.get("data", {}).get("data_table", [])
        
        for item in sessions:
            if item.get("lab_session_path") == target_path:
                session_id = item.get("lab_session_id")
                logger.debug(f"Found session ID {session_id} for path {target_path}")
                return session_id, None
        
        return None, f"Session not found for path {target_path}"
        
    except ValueError as exc:
        return None, f"JSON parse error: {str(exc)}"
    except Exception as exc:
        return None, f"Error getting session ID: {str(exc)}"



@retry_pnet_request(max_attempts=3)
def create_node(url, node_params, cookie, xsrf):
    r = requests.post(
        url + '/api/labs/session/nodes/add',
        json=node_params,
        cookies=cookie,
        verify=False,
        timeout=4  # 4 секунды таймаут для создания узла
    )
    if r.status_code in range(200, 400):
        logger.debug(
            "Node {} has been created\nServer response\t{}".format(node_params["template"], r.json()["message"]))
    return r


@retry_pnet_request(max_attempts=3)
def create_p2p(url, p2p_params, cookie):
    r = requests.post(
        url + '/api/labs/session/networks/p2p',
        json=p2p_params,
        cookies=cookie,
        verify=False,
        timeout=4  # 4 секунды таймаут для создания P2P соединения
    )
    if r.status_code in range(200, 400):
        logger.debug("P2P {} has been created \nServer response\t{}".format(p2p_params["name"], r.json()["message"]))
    return r


@retry_pnet_request(max_attempts=3)
def destroy_session(url, lab_session_id, cookie):
    lab_session_id = '{"lab_session":"' + str(lab_session_id) + '"}'
    r = requests.post(
        url + '/api/labs/session/factory/destroy',
        data=lab_session_id,
        headers={'content-type': 'application/json'},
        cookies=cookie, verify=False,
        timeout=6
    )
    logger.debug(r)
    return r


def leave_session(url, lab_session_id, cookie):
    """Покидает сессию лаборатории без уничтожения (wipe) и выключения нод"""
    lab_session_id = '{"lab_session":"' + str(lab_session_id) + '"}'
    r = requests.post(
        url + '/api/labs/session/factory/leave',
        data=lab_session_id,
        headers={'content-type': 'application/json'},
        cookies=cookie, verify=False,
        timeout=4
    )
    logger.debug(r)


@retry_pnet_request(max_attempts=3)
def create_network(url, net_params, cookie):
    r = requests.post(
        url + '/api/labs/session/networks/add',
        json=net_params,
        cookies=cookie,
        verify=False,
        timeout=4  # 4 секунды таймаут для создания сети
    )
    if r.status_code in range(200, 400):
        logger.debug(
            "Network {} has been created \nServer response\t{}".format(net_params["name"], r.json()["message"]))
    return r


@retry_pnet_request(max_attempts=3)
def create_p2p_nat(url, p2p_params, cookie):
    r = requests.post(
        url + '/api/labs/session/interfaces/edit',
        json=p2p_params,
        cookies=cookie,
        verify=False,
        timeout=4  # 4 секунды таймаут для редактирования интерфейса
    )
    if r.status_code in range(200, 400):
        logger.debug(
            "P2P_NAT {} has been created\nServer response\t{}".format(p2p_params["node_id"], r.json()["message"]))
    return r


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


def get_session_id(url, cookie):
        # Получаем session_id через /api/auth
    auth_response = get_auth_info(url, cookie)
    if auth_response.status_code != 200:
        logger.error(f"Failed to get auth info: {auth_response.status_code} - {auth_response.text}")
        raise Exception(f"Failed to get auth info: {auth_response.status_code}")
    
    auth_data = auth_response.json()
    if auth_data.get("code") != 200 or "data" not in auth_data:
        logger.error(f"Invalid auth response: {auth_data}")
        raise Exception(f"Invalid auth response: {auth_data}")

    data = auth_data["data"]
    sess_id = data.get("lab")
    if isinstance(sess_id, dict):
        sess_id = sess_id.get("id")
    if sess_id is None or sess_id == "":
        sess_id = data.get("session_id") or data.get("sessionId") or data.get("id") or data.get("pod")
    if sess_id is None or sess_id == "":
        keys = list(data.keys()) if isinstance(data, dict) else "not a dict"
        logger.error(f"Session ID not found in auth response. data keys: {keys}, full: {auth_data}")
        raise Exception(f"Session ID not found in PNET /api/auth response (data keys: {keys}).")
    logger.debug(f"Session ID obtained from /api/auth: {sess_id}")

    return sess_id


def create_all_lab_nodes_and_connectors(url, lab_object, lab_path, lab_name, cookie, xsrf, username, post_nodes_callback=None, usb_device_ids=None, pnet_login=None, session_manager=None):
    """
    Создание узлов и коннекторов лаборатории.
    
    Args:
        url: URL PNET сервера
        lab_object: Объект Lab
        lab_path: Путь к лаборатории
        lab_name: Имя лаборатории
        cookie: Cookie для аутентификации
        xsrf: XSRF токен
        username: Имя пользователя
        post_nodes_callback: Callback функция, вызываемая после создания нод, но до destroy_session.
                           Принимает (url, cookie, xsrf, sess_id) и должна вернуть данные для дальнейшей обработки
        usb_device_ids: Список USB device IDs для замены в qemu_options (например, [1, 2, 3])
        pnet_login: Логин PNet сессии для поиска сессии (если не указан, используется 'pnet_scripts')
        session_manager: Опциональный PNetSessionManager для автоматического повторного логина при 412
    """
    from interface.utils import replace_usb_device_ids_in_nodes
    
    username = slugify(username)
    lab_path += "/" + username

    lab_slash_name = "/" + lab_name
    lab = lab_path + lab_slash_name
    logger.debug(lab)

    # Вспомогательная функция для выполнения операций с автоматическим повторным логином
    def execute_with_reauth_if_needed(func, *args, **kwargs):
        """Выполняет функцию, при 412 обновляет cookie/xsrf из session_manager и повторяет"""
        if session_manager is None:
            # Если session_manager не передан, выполняем как обычно
            return func(*args, **kwargs)
        
        try:
            return func(*args, **kwargs)
        except UnauthorizedException:
            # Выполняем повторный логин в session_manager
            logger.warning("Unauthorized (412) detected, performing re-login")
            session_manager.force_relogin()  # Принудительный повторный логин
            
            # Получаем обновленные cookie и xsrf
            new_url, new_cookie, new_xsrf = session_manager.session_data
            
            # Обновляем локальные переменные
            nonlocal cookie, xsrf
            cookie = new_cookie
            xsrf = new_xsrf
            logger.info("Cookie and XSRF updated after re-login, retrying operation")
            
            # Обновляем аргументы функции для повторного вызова
            # Функции обычно принимают cookie и xsrf как позиционные аргументы после url
            updated_args = list(args)
            # Определяем позиции cookie и xsrf в аргументах на основе сигнатуры функции
            # create_node(url, node, cookie, xsrf) - cookie на позиции 2, xsrf на позиции 3
            # create_network(url, network, cookie) - cookie на позиции 2
            # create_p2p(url, connector, cookie) - cookie на позиции 2
            # create_p2p_nat(url, cloudConnector, cookie) - cookie на позиции 2
            # destroy_session(url, sess_id, cookie) - cookie на позиции 2
            
            # Обновляем cookie (обычно на позиции 2)
            if len(updated_args) >= 3:
                updated_args[2] = new_cookie
            # Обновляем xsrf (если есть, обычно на позиции 3)
            if len(updated_args) >= 4:
                updated_args[3] = new_xsrf
            
            # Обновляем через kwargs, если они есть
            updated_kwargs = dict(kwargs)
            if 'cookie' in updated_kwargs:
                updated_kwargs['cookie'] = new_cookie
            if 'xsrf' in updated_kwargs:
                updated_kwargs['xsrf'] = new_xsrf
            
            # Повторяем операцию с обновленными аргументами (только один раз)
            return func(*updated_args, **updated_kwargs)

    create_session(url, lab, cookie)
    # Сначала получаем session id по пути к лабе, иначе — из /api/auth
    sess_id, err = get_session_id_by_filter(url, cookie, xsrf, lab)
    if sess_id is None:
        sess_id = get_session_id(url, cookie)

    # Модифицируем NodesData с USB device IDs, если они предоставлены
    nodes_data = lab_object.NodesData
    if usb_device_ids:
        nodes_data = replace_usb_device_ids_in_nodes(nodes_data, usb_device_ids)

    for node in nodes_data:
        if node:
            execute_with_reauth_if_needed(create_node, url, node, cookie, xsrf)

    for network in lab_object.NetworksData:
        if network:
            execute_with_reauth_if_needed(create_network, url, network, cookie)

    for connector in lab_object.ConnectorsData:
        if connector:
            execute_with_reauth_if_needed(create_p2p, url, connector, cookie)

    for cloudConnector in lab_object.Connectors2CloudData:
        if cloudConnector:
            execute_with_reauth_if_needed(create_p2p_nat, url, cloudConnector, cookie)

    callback_result = None
    if post_nodes_callback:
        logger.info(f"Calling post_nodes_callback for {username}")
        try:
            callback_result = post_nodes_callback(url, cookie, xsrf, sess_id)
            logger.info(f"post_nodes_callback completed for {username}")
        except Exception as e:
            logger.error(f"Error in post_nodes_callback for {username}: {e}", exc_info=True)
    else:
        logger.debug(f"No post_nodes_callback provided for {username}")

    execute_with_reauth_if_needed(destroy_session, url, sess_id, cookie)
    
    return callback_result


def delete_lab_with_session_destroy(url: object, lab_name: object, lab_path: object, cookie: object, xsrf: object, username: object) -> object:
    username = slugify(username)
    lab_path += "/" + username

    lab_slash_name = "/" + lab_name
    lab = lab_path + lab_slash_name
    logger.debug(lab)

    response_json = filter_session(url, cookie, xsrf, 1, 25, path_contains=lab + '.unl')

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
            destroy_session(url, item["lab_session_id"], cookie)

    r = delete_lab(url, cookie, lab).json()
    logger.debug(r)


def get_lab_topology(url, cookie):
    """Получает топологию лаборатории из PNET"""
    try:
        response = requests.get(
            f"{url}/api/labs/session/topology",
            cookies=cookie,
            verify=False,
            timeout=10
        )

        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Failed to get lab topology: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logger.error(f"Error getting lab topology: {str(e)}")
        return None


def get_guacamole_url(url, node_id, cookie):
    """Получает ссылку на Guacamole консоль для указанной ноды"""
    try:
        response = requests.get(
            f"{url}/api/labs/session/console_guac_link?&node_id={node_id}",
            cookies=cookie,
            verify=False,
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            if data.get('code') == 200 and 'data' in data:
                # Нормализуем URL, добавляя базовый URL PNET
                guac_path = data['data']
                if guac_path.startswith('/'):
                    guac_path = guac_path[1:]
                return f"{url}/{guac_path}"
            else:
                logger.error(f"Invalid response format: {data}")
                return None
        else:
            logger.error(f"Failed to get guacamole URL: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logger.error(f"Error getting guacamole URL: {str(e)}")
        return None


def login_user_to_pnet(url, username, password):
    """
    Логинит пользователя в PNET и возвращает session с cookies.
    Использует requests.Session() для правильного сохранения cookies.
    
    Args:
        url: URL PNET сервера
        username: Имя пользователя PNET
        password: Пароль пользователя PNET
    
    Returns:
        tuple: (session, xsrf_token) где session - requests.Session с установленными cookies
               или (None, None) при ошибке
    """
    try:
        session = requests.Session()
        session.verify = False
        
        # Получаем XSRF-TOKEN
        preflight_response = session.get(f"{url}/store/public/auth/login/login", timeout=10)
        if preflight_response.status_code not in [200, 202]:
            logger.error(f"Failed to connect to PNET for preflight: {preflight_response.status_code}")
            return None, None
        
        xsrf_token = session.cookies.get('XSRF-TOKEN', '')
        
        # Аутентификация
        headers = {'Content-Type': 'application/json;charset=UTF-8', 'X-Requested-With': 'XMLHttpRequest'}
        if xsrf_token:
            headers['X-XSRF-TOKEN'] = xsrf_token
        
        login_response = session.post(
            f"{url}/store/public/auth/login/login",
            headers=headers,
            json={'username': username, 'password': password, 'html': '0', 'captcha': ''},
            timeout=10
        )
        
        if login_response.status_code not in [200, 201, 202]:
            logger.error(f"PNET authentication failed: {login_response.status_code} - {login_response.text}")
            return None, None
        
        # Проверка JSON ответа для статуса 202
        if login_response.status_code == 202:
            try:
                response_data = login_response.json()
                if not response_data.get('result', False):
                    logger.error(f"PNET authentication failed: {response_data}")
                    return None, None
            except (ValueError, KeyError):
                pass  # Продолжаем, возможно cookies установлены
        
        logger.info(f"Successfully logged in to PNET as {username}")
        return session, xsrf_token
    
    except requests.exceptions.Timeout:
        logger.error("PNET login timeout")
        return None, None
    except requests.exceptions.ConnectionError:
        logger.error("Failed to connect to PNET for login")
        return None, None
    except Exception as e:
        logger.error(f"Error logging in to PNET: {str(e)}")
        return None, None


def create_pnet_lab_session_common(url, user_pnet_login, lab_path, cookie):
    """Общая логика создания сессии лаборатории в PNET"""
    try:
        # Создаем сессию лабы
        full_url = f"{url}/api/labs/session/factory/create"
        payload = {'path': lab_path}

        create_session_response = requests.post(
            full_url,
            headers={
                'Content-Type': 'application/json;charset=UTF-8',
                'Accept': 'application/json, text/plain, */*',
                'Referer': f"{url}/store/public/admin/main/view",
                'X-Requested-With': 'XMLHttpRequest'
            },
            json=payload,
            cookies=cookie,
            timeout=10,
            verify=False
        )

        if create_session_response.status_code != 200:
            logger.error(f"Failed to create lab session: {create_session_response.text}")
            return False, f"Failed to create lab session: {create_session_response.text}"

        return True, "Lab session created successfully"

    except requests.exceptions.Timeout:
        logger.error("PNET request timeout")
        return False, "PNET request timeout"
    except requests.exceptions.ConnectionError:
        logger.error("Failed to connect to PNET")
        return False, "Failed to connect to PNET"
    except Exception as e:
        logger.error(f"Session creation error: {str(e)}")
        return False, f"Session creation error: {str(e)}"


def turn_on_node(url, node_id, cookie):
    """Включает ноду в PNET"""
    try:
        response = requests.post(
            f"{url}/api/labs/session/nodes/start",
            headers={
                'Content-Type': 'application/json;charset=UTF-8',
                'Accept': 'application/json, text/plain, */*',
                'X-Requested-With': 'XMLHttpRequest'
            },
            json={'id': str(node_id)},
            cookies=cookie,
            verify=False,
            timeout=10
        )

        if response.status_code == 200:
            try:
                response_data = response.json()
                logger.info(f"Node {node_id} start response: {response_data}")
            except:
                logger.info(f"Node {node_id} start response (non-JSON): {response.text[:200]}")
            logger.info(f"Node {node_id} started successfully")
            return True, "Node started successfully"
        else:
            logger.error(f"Failed to start node {node_id}: {response.status_code} - {response.text}")
            return False, f"Failed to start node: {response.text}"

    except requests.exceptions.Timeout:
        logger.error(f"Timeout starting node {node_id}")
        return False, "Node start timeout"
    except requests.exceptions.ConnectionError:
        logger.error(f"Connection error starting node {node_id}")
        return False, "Failed to connect to PNET"
    except Exception as e:
        logger.error(f"Error starting node {node_id}: {str(e)}")
        return False, f"Node start error: {str(e)}"


def get_node_status(url, node_id, cookie):
    """
    Получает статус ноды из PNET.
    
    Args:
        url: URL PNET сервера
        node_id: ID ноды
        cookie: Cookie для аутентификации
    
    Returns:
        int или None: Статус ноды (0=stopped, 1=starting, 2=ready) или None при ошибке
    """
    try:
        response = requests.post(
            f"{url}/api/labs/session/nodestatus",
            headers={
                'Content-Type': 'application/json;charset=UTF-8',
                'Accept': 'application/json, text/plain, */*',
                'X-Requested-With': 'XMLHttpRequest'
            },
            json={},
            cookies=cookie,
            verify=False,
            timeout=10
        )

        if response.status_code == 200:
            try:
                response_data = response.json()
                if response_data.get('code') == 200 and 'data' in response_data:
                    data = response_data['data']
                    node_id_str = str(node_id)
                    if node_id_str in data:
                        status = data[node_id_str]
                        return int(status)
                    else:
                        logger.warning(f"Node {node_id} not found in nodestatus response: {data}")
                        return None
                else:
                    logger.error(f"Invalid nodestatus response format: {response_data}")
                    return None
            except (ValueError, KeyError) as e:
                logger.error(f"Error parsing nodestatus response: {e}, response: {response.text[:200]}")
                return None
        else:
            logger.error(f"Failed to get node status: {response.status_code} - {response.text}")
            return None

    except requests.exceptions.Timeout:
        logger.error(f"Timeout getting node {node_id} status")
        return None
    except requests.exceptions.ConnectionError:
        logger.error(f"Connection error getting node {node_id} status")
        return None
    except Exception as e:
        logger.error(f"Error getting node {node_id} status: {str(e)}")
        return None
