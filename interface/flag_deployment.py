import logging
import time
import threading
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, List
from concurrent.futures import ThreadPoolExecutor, Future

from interface.ssh_manager import process_ssh_tasks, create_ssh_tasks_for_lab_nodes
from interface.eveFunctions import (
    get_node_status, login_user_to_pnet, create_pnet_lab_session_common, get_lab_topology,
    get_session_id, turn_on_node, leave_session
)
from interface.flag_generator import generate_flags_for_tasks
from interface.lab_topology import LabTopology
from interface.config import get_pnet_url

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Статус задачи развертывания флагов"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


@dataclass
class FlagDeploymentTask:
    """
    Задача для развертывания флагов.
    Полностью сериализуемая, не требует доступа к БД.
    Спроектирован для легкого перехода на Celery.
    """
    task_id: str
    # Данные пользователя
    pnet_login: str
    pnet_password: str
    # Путь к лаборатории в PNET
    lab_path: str
    # Данные флагов
    generated_flags: Dict
    # Данные нод лаборатории
    lab_nodes: List[Dict[str, str]]  # [{'node_name': ..., 'login': ..., 'password': ...}, ...]
    # Метаданные для логирования
    competition_slug: str
    instance_type: str  # 'Competition2User' или 'TeamCompetition2Team'
    instance_id: int
    # Статус выполнения
    status: TaskStatus = TaskStatus.PENDING
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    _future: Optional[Future] = field(default=None, repr=False)


class FlagDeploymentQueue:
    """
    Глобальный менеджер очереди задач развертывания флагов.
    Использует ThreadPoolExecutor для параллельного выполнения.
    В будущем можно заменить на Celery, сохранив интерфейс.
    """
    
    def __init__(self, max_workers: int = 10):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="flag_deploy")
        self._tasks: Dict[str, FlagDeploymentTask] = {}
        self._lock = threading.Lock()
    
    def submit_task(self, task: FlagDeploymentTask) -> None:
        """Добавляет задачу в очередь на выполнение"""
        with self._lock:
            self._tasks[task.task_id] = task
            task.status = TaskStatus.PENDING
        
        future = self.executor.submit(self._execute_task, task)
        task._future = future
        
        with self._lock:
            task.status = TaskStatus.RUNNING
    
    def _execute_task(self, task: FlagDeploymentTask) -> None:
        """Выполняет задачу развертывания флагов без обращения к БД"""
        try:
            # Все данные уже в task, БД не нужна
            _deploy_flags_to_lab_from_task(task)
            
            task.status = TaskStatus.SUCCESS
            task.completed_at = time.time()
            
        except Exception as e:
            logger.error(f"Error executing flag deployment task {task.task_id}: {e}", exc_info=True)
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = time.time()
    
    def get_tasks_by_competition(self, competition_slug: str) -> List[FlagDeploymentTask]:
        """Возвращает все задачи для указанного соревнования"""
        with self._lock:
            return [
                task for task in self._tasks.values()
                if task.competition_slug == competition_slug
            ]
    
    def wait_for_tasks(self, task_ids: List[str], timeout: Optional[float] = None) -> Dict[str, FlagDeploymentTask]:
        """
        Ожидает завершения указанных задач.
        
        Args:
            task_ids: Список ID задач для ожидания
            timeout: Максимальное время ожидания в секундах (None = без ограничений)
        
        Returns:
            Словарь {task_id: task} с результатами
        """
        start_time = time.time()
        results = {}
        
        with self._lock:
            futures = {
                task_id: self._tasks[task_id]._future
                for task_id in task_ids
                if task_id in self._tasks and self._tasks[task_id]._future is not None
            }
        
        for task_id, future in futures.items():
            if timeout:
                remaining = timeout - (time.time() - start_time)
                if remaining <= 0:
                    break
                try:
                    future.result(timeout=remaining)
                except Exception:
                    pass
            else:
                try:
                    future.result()
                except Exception:
                    pass
            
            with self._lock:
                if task_id in self._tasks:
                    results[task_id] = self._tasks[task_id]
        
        return results
    
    def cleanup_old_tasks(self, max_age_seconds: float = 3600) -> None:
        """Удаляет старые завершенные задачи из памяти"""
        current_time = time.time()
        with self._lock:
            to_remove = [
                task_id for task_id, task in self._tasks.items()
                if task.completed_at and (current_time - task.completed_at) > max_age_seconds
            ]
            for task_id in to_remove:
                del self._tasks[task_id]
    
    def shutdown(self, wait: bool = True) -> None:
        """Останавливает executor"""
        self.executor.shutdown(wait=wait)


# Глобальный экземпляр очереди
_global_queue: Optional[FlagDeploymentQueue] = None
_queue_lock = threading.Lock()


def get_flag_deployment_queue() -> FlagDeploymentQueue:
    """Получает глобальный экземпляр очереди"""
    global _global_queue
    with _queue_lock:
        if _global_queue is None:
            _global_queue = FlagDeploymentQueue(max_workers=10)
        return _global_queue


def deploy_flags(ssh_nodes, flags_config, pnet_url, lab_nodes_db):
    """Размещает флаги на нодах лаборатории через SSH"""
    ssh_tasks = create_ssh_tasks_for_lab_nodes(ssh_nodes, flags_config, pnet_url, lab_nodes_db)
    if ssh_tasks:
        process_ssh_tasks(ssh_tasks)


def _prepare_flags_config(generated_flags):
    """Преобразует generated_flags в словарь flags_config"""
    if isinstance(generated_flags, dict):
        return generated_flags
    if isinstance(generated_flags, list):
        return {
            item.get('task_id'): item.get('flag')
            for item in generated_flags
            if isinstance(item, dict) and item.get('task_id') and item.get('flag')
        }
    return {}


@contextmanager
def _pnet_session_context(pnet_url, pnet_login, pnet_password, lab_path):
    """Context manager для управления PNET сессией"""
    session, xsrf = login_user_to_pnet(pnet_url, pnet_login, pnet_password)
    if not session:
        yield None, None
        return
    
    success, _ = create_pnet_lab_session_common(pnet_url, pnet_login, lab_path, session.cookies, xsrf)
    if not success:
        yield None, None
        return
    
    sess_id = get_session_id(pnet_url, session.cookies)
    try:
        yield session, sess_id
    finally:
        leave_session(pnet_url, sess_id, session.cookies)


def _deploy_flags_to_lab_from_task(task: FlagDeploymentTask):
    """
    Развертывание флагов на лаборатории из данных задачи.
    Не требует доступа к БД - все данные в task.
    """
    pnet_url = get_pnet_url()
    if not pnet_url or not task.lab_nodes:
        return
    
    flags_config = _prepare_flags_config(task.generated_flags)
    if not flags_config:
        return
    
    try:
        with _pnet_session_context(pnet_url, task.pnet_login, task.pnet_password, task.lab_path) as (session, sess_id):
            if not session or not sess_id:
                return
            
            topology_data = get_lab_topology(pnet_url, session.cookies)
            if not topology_data:
                return
            
            topology = LabTopology(topology_data)
            ssh_nodes = topology.get_ssh_nodes()
            if not ssh_nodes:
                return
            
            # Включаем ноды
            node_name_to_id = {node['name']: node['id'] for node in ssh_nodes}
            for lab_node in task.lab_nodes:
                node_name = lab_node['node_name']
                if node_name in node_name_to_id:
                    node_id = node_name_to_id[node_name]
                    turn_on_node(pnet_url, node_id, session.cookies)
                    wait_for_node_ready(pnet_url, node_id, session.cookies, max_wait_time=15)
            
            # Размещаем флаги
            deploy_flags(ssh_nodes, flags_config, pnet_url, task.lab_nodes)
        
    except Exception as e:
        logger.error(f"Error deploying flags for task {task.task_id}: {e}", exc_info=True)
        raise


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


def generate_and_save_flags(instance, tasks):
    """Генерирует флаги для заданий и сохраняет их в instance"""
    flags = generate_flags_for_tasks(tasks)
    instance.generated_flags = flags
    instance.save(update_fields=['generated_flags'])


def create_flag_deployment_task(instance, user, lab, competition_slug, instance_type):
    """
    Создает задачу развертывания флагов.
    
    Args:
        instance: Competition2User или TeamCompetition2Team
        user: User объект с pnet_login и pnet_password
        lab: Lab объект
        competition_slug: slug соревнования
        instance_type: 'Competition2User' или 'TeamCompetition2Team'
    
    Returns:
        FlagDeploymentTask или None, если задача не может быть создана
    """
    from interface.api import get_lab_path
    
    if not lab.nodes.exists():
        return None
    
    lab_nodes = list(lab.nodes.values('node_name', 'login', 'password'))
    lab_path = get_lab_path(instance.competition, user)
    
    return FlagDeploymentTask(
        task_id=str(uuid.uuid4()),
        pnet_login=user.pnet_login,
        pnet_password=user.pnet_password,
        lab_path=lab_path,
        generated_flags=instance.generated_flags,
        lab_nodes=lab_nodes,
        competition_slug=competition_slug,
        instance_type=instance_type,
        instance_id=instance.id
    )
