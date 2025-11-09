import io
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List

from fabric import Connection
from fabric.transfer import Transfer
import paramiko
import socket
from invoke.exceptions import UnexpectedExit

logger = logging.getLogger(__name__)


class SSHConnectionTask:
    """Задача для SSH подключения и размещения флагов"""
    
    def __init__(self, host: str, port: str, username: str, password: str, 
                 flags_config: dict, node_name: str):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.flags_config = flags_config
        self.node_name = node_name
        self.result = None
        self.error = None
    
    def execute(self) -> tuple[bool, str]:
        """Выполняет SSH подключение и размещение файла с ретраями"""
        max_total_time = 30
        start_time = time.time()
        attempt = 0
        base_delay = 2
        full_host = f"{self.host}:{self.port}"
        
        while time.time() - start_time < max_total_time:
            attempt += 1
            try:
                remaining_time = max_total_time - (time.time() - start_time)
                conn = Connection(
                    host=full_host,
                    user=self.username,
                    connect_kwargs={'password': self.password},
                    connect_timeout=min(10, remaining_time)
                )
                
                with conn:
                    config_content = json.dumps(self.flags_config, indent=4)
                    
                    # Определяем путь для конфига
                    id_result = conn.run('id -u', hide=True, warn=True)
                    is_root = not id_result.failed and id_result.stdout.strip() == '0'
                    
                    if is_root:
                        config_dir = '/etc/configs'
                        use_sudo = False
                    else:
                        sudo_check = conn.run('which sudo', hide=True, warn=True)
                        has_sudo = not sudo_check.failed and sudo_check.stdout.strip()
                        if has_sudo:
                            config_dir = '/etc/configs'
                            use_sudo = True
                        else:
                            home_result = conn.run('echo $HOME', hide=True, warn=True)
                            home_dir = home_result.stdout.strip() if not home_result.failed and home_result.stdout.strip() else f'/home/{self.username}'
                            config_dir = f'{home_dir}/configs'
                            use_sudo = False
                    
                    config_file = f'{config_dir}/checker_conf.json'
                    temp_file = '/tmp/checker_conf.json'
                    
                    # Создаем директорию и размещаем файл
                    if use_sudo:
                        conn.sudo(f'mkdir -p {config_dir}', password=self.password, hide=True, warn=True)
                    else:
                        conn.run(f'mkdir -p {config_dir}', hide=True, warn=True)
                    
                    transfer = Transfer(conn)
                    transfer.put(io.BytesIO(config_content.encode('utf-8')), temp_file)
                    
                    if use_sudo:
                        conn.sudo(f'mv {temp_file} {config_file}', password=self.password, hide=True, warn=True)
                        conn.sudo(f'chmod 600 {config_file}', password=self.password, hide=True, warn=True)
                        conn.sudo(f'chown {self.username}:{self.username} {config_file}', password=self.password, hide=True, warn=True)
                    else:
                        conn.run(f'mv {temp_file} {config_file}', hide=True, warn=True)
                        conn.run(f'chmod 600 {config_file}', hide=True, warn=True)
                        conn.run(f'chown {self.username}:{self.username} {config_file}', hide=True, warn=True)
                    
                    logger.info(f"Flags placed on {self.node_name} at {config_file}")
                    return True, f"Flags placed on {self.node_name}"
            
            except (paramiko.AuthenticationException, paramiko.BadAuthenticationType) as e:
                if attempt == 1:
                    return False, f"Authentication failed: {str(e)}"
            except (UnexpectedExit, paramiko.SSHException, socket.error, socket.timeout, OSError, ConnectionError, TimeoutError, Exception) as e:
                elapsed = time.time() - start_time
                if elapsed >= max_total_time:
                    return False, f"Failed after {attempt} attempts: {str(e)}"
                delay = min(base_delay * (2 ** (attempt - 1)), max_total_time - elapsed)
                time.sleep(delay)
        
        return False, f"Failed after {attempt} attempts"


def process_ssh_tasks(tasks: List[SSHConnectionTask], max_workers: int = 10) -> List[SSHConnectionTask]:
    """Обрабатывает список SSH задач параллельно"""
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(task.execute): task for task in tasks}
        
        for future in as_completed(futures):
            task = futures[future]
            try:
                success, message = future.result()
                task.result = success
                task.error = message if not success else None
            except Exception as e:
                task.result = False
                task.error = str(e)
    
    return tasks


def create_ssh_tasks_for_lab_nodes(
    lab_nodes: List[Dict],
    flags_config: dict,
    pnet_url: str,
    lab_node_configs: List[Dict]
) -> List[SSHConnectionTask]:
    """Создает SSH задачи для размещения флагов на нодах лаборатории"""
    tasks = []
    pnet_host = pnet_url.replace('http://', '').replace('https://', '').split(':')[0]
    node_config_map = {config['node_name']: config for config in lab_node_configs}
    
    for node in lab_nodes:
        node_name = node['name']
        if node_name not in node_config_map:
            continue
        
        config = node_config_map[node_name]
        task = SSHConnectionTask(
            host=pnet_host,
            port=str(node['port']),
            username=config['login'],
            password=config['password'],
            flags_config=flags_config,
            node_name=node_name
        )
        tasks.append(task)
    
    return tasks
