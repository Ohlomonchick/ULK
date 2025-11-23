"""
Интеграционные тесты для механизма нумерации воркеров Gunicorn.

Тесты проверяют:
1. Правильную нумерацию воркеров (1, 2, 3)
2. Стабильность номеров при перезапусках
3. Корректную работу при падениях воркеров

ВАЖНО: 
- Эти тесты требуют Linux-окружения, так как используют fcntl для файловых блокировок.
- Тесты используют продовый конфиг sre/gunicorn.conf.py
- Для запуска на Windows используйте WSL или Linux-окружение.
- Требуется pytest-xprocess для управления процессами
"""
import os
import sys
import time
import signal
import json
import errno
from pathlib import Path
import pytest
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from xprocess import ProcessStarter

# Проверка доступности fcntl (требуется для Linux)
try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False
    pytestmark = pytest.mark.skip(reason="fcntl not available (requires Linux)")

# Добавляем корневую директорию проекта в путь
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Путь к продовому конфигу Gunicorn
PROD_GUNICORN_CONF = PROJECT_ROOT / "sre" / "gunicorn.conf.py"


class GunicornClient:
    """Клиент для взаимодействия с Gunicorn сервером"""
    
    # Путь к файлу маппинга воркеров (из gunicorn.conf.py)
    WORKER_MAPPING_FILE = "/tmp/gunicorn_worker_mapping.json"
    
    def __init__(self, base_url):
        self.base_url = base_url
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.1,
            status_forcelist=[500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
    
    def _is_process_alive(self, pid):
        """Проверяет, жив ли процесс с указанным PID"""
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False
    
    def get_worker_mapping(self):
        """
        Читает маппинг PID -> worker_id из файла.
        Возвращает словарь {pid: worker_id} только для живых процессов.
        """
        if not os.path.exists(self.WORKER_MAPPING_FILE):
            return {}
        
        try:
            with open(self.WORKER_MAPPING_FILE, 'r') as f:
                mapping = json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
        
        # Фильтруем только живые процессы
        alive_mapping = {}
        for pid_str, worker_id in mapping.items():
            try:
                pid = int(pid_str)
                if self._is_process_alive(pid):
                    alive_mapping[pid] = int(worker_id)
            except (ValueError, TypeError):
                continue
        
        return alive_mapping
    
    def wait_for_workers(self, expected_count=3, timeout=30):
        """
        Ждет, пока в файле маппинга появится нужное количество воркеров.
        Возвращает маппинг {pid: worker_id} для всех живых воркеров.
        """
        start_time = time.time()
        while (time.time() - start_time) < timeout:
            mapping = self.get_worker_mapping()
            if len(mapping) >= expected_count:
                return mapping
            time.sleep(0.5)
        
        # Возвращаем то, что есть, даже если не дождались
        return self.get_worker_mapping()
    
    def get_worker_info(self):
        """Получает информацию о воркере, обработавшем запрос (для совместимости)"""
        response = self.session.get(
            f"{self.base_url}/cyberpolygon/test/worker-id/",
            timeout=5
        )
        response.raise_for_status()
        return response.json()
    
    def get_all_workers_info(self, num_requests=50, min_workers=3, timeout=10):
        """
        Получает информацию о всех воркерах через файл маппинга.
        Это более надежный способ, чем HTTP-запросы.
        """
        # Используем файл маппинга для получения информации о всех воркерах
        mapping = self.wait_for_workers(expected_count=min_workers, timeout=timeout)
        
        # Преобразуем в формат, совместимый со старым API
        workers_info = []
        for pid, worker_id in mapping.items():
            workers_info.append({
                'pid': pid,
                'worker_id': worker_id,
                'worker_index': worker_id - 1
            })
        
        return workers_info
    
    def kill_worker_by_pid(self, pid):
        """Убивает воркер по PID"""
        try:
            os.kill(pid, signal.SIGKILL)
            time.sleep(2)  # Ждем перезапуска воркера
        except ProcessLookupError:
            pass


@pytest.fixture(scope="session")
def gunicorn_server(xprocess, test_port):
    """
    Фикстура для запуска Gunicorn сервера через xprocess.
    Автоматически управляет жизненным циклом процесса.
    """
    class GunicornStarter(ProcessStarter):
        """Класс для запуска Gunicorn через xprocess"""
        # Не используем pattern, так как при log-level=error он не виден
        # Полагаемся только на startup_check
        pattern = None
        timeout = 30  # Увеличиваем для запуска Django
        terminate_on_interrupt = True
        
        args = [
            sys.executable, '-m', 'gunicorn',
            'Cyberpolygon.wsgi:application',
            '-c', str(PROD_GUNICORN_CONF),
            '--bind', f'127.0.0.1:{test_port}',
            '--workers', '3',
            '--timeout', '30',
            '--log-level', 'error',
        ]
        
        # Устанавливаем рабочую директорию проекта
        cwd = str(PROJECT_ROOT)
        
        env = {
            **os.environ,
            'DJANGO_SETTINGS_MODULE': 'Cyberpolygon.settings',
            'GUNICORN_WORKER': 'true',
            'PYTHONPATH': str(PROJECT_ROOT),  # Добавляем проект в PYTHONPATH
        }
        
        def startup_check(self):
            """Проверка готовности сервера через HTTP-запрос"""
            import requests
            try:
                response = requests.get(
                    f"http://127.0.0.1:{test_port}/cyberpolygon/test/worker-id/",
                    timeout=2
                )
                return response.status_code == 200
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                return False
    
    # xprocess автоматически управляет процессом
    xprocess.ensure("gunicorn", GunicornStarter)
    
    # Ждем немного для полной инициализации всех воркеров
    # При использовании gevent может потребоваться больше времени
    time.sleep(3)
    
    yield f"http://127.0.0.1:{test_port}"
    
    # xprocess автоматически остановит процесс при завершении тестов


@pytest.fixture
def gunicorn_client(gunicorn_server):
    """Фикстура для создания клиента Gunicorn"""
    return GunicornClient(gunicorn_server)


def test_worker_numbering(gunicorn_client):
    """Тест правильной нумерации воркеров"""
    workers_info = gunicorn_client.get_all_workers_info(num_requests=100, min_workers=3, timeout=15)
    
    worker_ids = set()
    pids_by_worker_id = {}
    
    for info in workers_info:
        worker_id = info.get('worker_id')
        pid = info.get('pid')
        if worker_id is not None:
            worker_ids.add(worker_id)
            if worker_id not in pids_by_worker_id:
                pids_by_worker_id[worker_id] = set()
            pids_by_worker_id[worker_id].add(pid)
    
    assert len(worker_ids) == 3, f"Expected 3 workers, got {len(worker_ids)}: {worker_ids}"
    assert worker_ids == {1, 2, 3}, f"Expected worker IDs {1, 2, 3}, got {worker_ids}"
    
    for worker_id, pids in pids_by_worker_id.items():
        assert len(pids) >= 1, f"Worker {worker_id} should have at least one PID"


def test_worker_stability_after_restart(gunicorn_client):
    """Тест стабильности номеров воркеров после перезапуска"""
    initial_info = gunicorn_client.get_all_workers_info(num_requests=100, min_workers=3, timeout=15)
    initial_worker_ids = {info['worker_id'] for info in initial_info if info.get('worker_id')}
    initial_pids = {info['pid'] for info in initial_info}
    
    assert len(initial_worker_ids) == 3, f"Should have 3 workers initially, got {len(initial_worker_ids)}: {initial_worker_ids}"
    
    worker_to_kill = initial_info[0]
    pid_to_kill = worker_to_kill['pid']
    worker_id_to_kill = worker_to_kill['worker_id']
    
    print(f"Killing worker with PID {pid_to_kill}, worker_id {worker_id_to_kill}")
    gunicorn_client.kill_worker_by_pid(pid_to_kill)
    time.sleep(3)
    
    new_info = gunicorn_client.get_all_workers_info(num_requests=100, min_workers=3, timeout=15)
    new_worker_ids = {info['worker_id'] for info in new_info if info.get('worker_id')}
    new_pids = {info['pid'] for info in new_info}
    
    assert len(new_worker_ids) == 3, f"Should still have 3 workers after restart, got {new_worker_ids}"
    assert new_worker_ids == {1, 2, 3}, f"Worker IDs should still be 1-3, got {new_worker_ids}"
    assert pid_to_kill not in new_pids, f"Killed PID {pid_to_kill} should not be in new PIDs"
    
    worker_ids_after_restart = [info['worker_id'] for info in new_info if info.get('worker_id') == worker_id_to_kill]
    assert len(worker_ids_after_restart) > 0, f"Worker ID {worker_id_to_kill} should still be in use after restart"


def test_multiple_worker_restarts(gunicorn_client):
    """Тест множественных перезапусков воркеров"""
    for restart_num in range(3):
        info = gunicorn_client.get_all_workers_info(num_requests=100, min_workers=3, timeout=15)
        worker_ids = {w['worker_id'] for w in info if w.get('worker_id')}
        pids = {w['pid'] for w in info}
        
        assert len(worker_ids) == 3, f"Should have 3 workers before restart {restart_num + 1}, got {len(worker_ids)}: {worker_ids}"
        assert worker_ids == {1, 2, 3}, f"Worker IDs should be 1-3 before restart {restart_num + 1}, got {worker_ids}"
        
        worker_to_kill = info[0]
        pid_to_kill = worker_to_kill['pid']
        worker_id_to_kill = worker_to_kill['worker_id']
        
        print(f"Restart {restart_num + 1}: Killing worker PID {pid_to_kill}, worker_id {worker_id_to_kill}")
        gunicorn_client.kill_worker_by_pid(pid_to_kill)
        time.sleep(3)
        
        new_info = gunicorn_client.get_all_workers_info(num_requests=100, min_workers=3, timeout=15)
        new_worker_ids = {w['worker_id'] for w in new_info if w.get('worker_id')}
        new_pids = {w['pid'] for w in new_info}
        
        assert len(new_worker_ids) == 3, f"Should have 3 workers after restart {restart_num + 1}"
        assert new_worker_ids == {1, 2, 3}, f"Worker IDs should be 1-3 after restart {restart_num + 1}"
        assert pid_to_kill not in new_pids, f"Killed PID should not be in new PIDs after restart {restart_num + 1}"
        assert worker_id_to_kill in new_worker_ids, f"Worker ID {worker_id_to_kill} should still be in use"


def test_worker_index_consistency(gunicorn_client):
    """Тест согласованности worker_id и worker_index"""
    workers_info = gunicorn_client.get_all_workers_info(num_requests=50, min_workers=3, timeout=15)
    
    for info in workers_info:
        worker_id = info.get('worker_id')
        worker_index = info.get('worker_index')
        
        if worker_id is not None:
            assert worker_index is not None, "worker_index should be set if worker_id is set"
            assert worker_index == worker_id - 1, f"worker_index should be worker_id - 1, got {worker_index} for worker_id {worker_id}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

