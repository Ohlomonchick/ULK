import logging
import time

from interface.ssh_manager import process_ssh_tasks, create_ssh_tasks_for_lab_nodes
from interface.eveFunctions import (
    get_node_status, filter_user, get_sessions_count, filter_session,
    login_user_to_pnet, create_pnet_lab_session_common, get_lab_topology,
    join_session, turn_on_node, leave_session
)
from interface.flag_generator import generate_flags_for_tasks
from interface.lab_topology import LabTopology
from interface.config import get_pnet_url
from interface.api import get_lab_path

logger = logging.getLogger(__name__)


def deploy_flags(ssh_nodes, flags_config, pnet_url, lab_nodes_db):
    """Размещает флаги на нодах лаборатории через SSH"""
    ssh_tasks = create_ssh_tasks_for_lab_nodes(ssh_nodes, flags_config, pnet_url, lab_nodes_db)
    if ssh_tasks:
        process_ssh_tasks(ssh_tasks)


def _deploy_flags_to_lab(instance, user, competition, lab):
    """Общая функция для развертывания флагов на лаборатории"""
    from interface.models import LabNode
    
    pnet_url = get_pnet_url()
    if not pnet_url:
        return
    
    if not lab.nodes.exists():
        return
    
    try:
        session, xsrf = login_user_to_pnet(pnet_url, user.pnet_login, user.pnet_password)
        if not session:
            return
        
        lab_path = get_lab_path(competition, user)
        success, _ = create_pnet_lab_session_common(pnet_url, user.pnet_login, lab_path, session.cookies)
        if not success:
            return
        
        sess_id = get_lab_session_id(pnet_url, lab_path, session.cookies, xsrf)
        if not sess_id:
            return
        
        join_session(pnet_url, sess_id, session.cookies)
        
        topology_data = get_lab_topology(pnet_url, session.cookies)
        if not topology_data:
            leave_session(pnet_url, sess_id, session.cookies)
            return
        
        topology = LabTopology(topology_data)
        ssh_nodes = topology.get_ssh_nodes()
        if not ssh_nodes:
            leave_session(pnet_url, sess_id, session.cookies)
            return
        
        lab_nodes_db = list(LabNode.objects.filter(lab=lab).values('node_name', 'login', 'password'))
        if not lab_nodes_db:
            leave_session(pnet_url, sess_id, session.cookies)
            return
        
        # Включаем ноды
        node_name_to_id = {node['name']: node['id'] for node in ssh_nodes}
        for lab_node in lab_nodes_db:
            node_name = lab_node['node_name']
            if node_name in node_name_to_id:
                node_id = node_name_to_id[node_name]
                turn_on_node(pnet_url, node_id, session.cookies)
                wait_for_node_ready(pnet_url, node_id, session.cookies, max_wait_time=15)
        
        # Подготавливаем флаги
        if isinstance(instance.generated_flags, list):
            flags_config = {item.get('task_id'): item.get('flag') for item in instance.generated_flags if isinstance(item, dict)}
        elif isinstance(instance.generated_flags, dict):
            flags_config = instance.generated_flags
        else:
            leave_session(pnet_url, sess_id, session.cookies)
            return
        
        if not flags_config:
            leave_session(pnet_url, sess_id, session.cookies)
            return
        
        # Размещаем флаги
        deploy_flags(ssh_nodes, flags_config, pnet_url, lab_nodes_db)
        leave_session(pnet_url, sess_id, session.cookies)
        
    except Exception as e:
        logger.error(f"Error deploying flags: {e}", exc_info=True)


def get_lab_session_id(url, lab_path, cookie, xsrf):
    """Получает session_id для лаборатории по пути"""
    try:
        users = filter_user(url, cookie, xsrf).json()
        r = get_sessions_count(url, cookie).json()
        count_labs = r["data"]
        response_json = filter_session(url, cookie, xsrf, 1, count_labs).json()
        
        for item in response_json["data"]["data_table"]:
            if item["lab_session_path"] == lab_path:
                return item["lab_session_id"]
        return None
    except Exception as e:
        logger.error(f"Error getting session ID: {e}", exc_info=True)
        return None


def wait_for_node_ready(url, node_id, cookie, max_wait_time=15):
    """Ожидает готовности ноды после включения"""
    start_time = time.time()
    check_interval = 2
    
    while time.time() - start_time < max_wait_time:
        node_status = get_node_status(url, node_id, cookie)
        if node_status == 2:
            return True
        time.sleep(check_interval)
    
    return False


def generate_and_save_flags(competition2user, tasks):
    """Генерирует флаги для заданий и сохраняет их в competition2user"""
    flags = generate_flags_for_tasks(tasks)
    competition2user.generated_flags = flags
    competition2user.save(update_fields=['generated_flags'])
