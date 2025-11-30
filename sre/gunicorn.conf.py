# gunicorn.conf.py
import os
import json
import fcntl
import errno

# Устанавливаем флаг для wsgi.py чтобы он знал что запущен через Gunicorn
os.environ['GUNICORN_WORKER'] = 'true'

# Non logging stuff
bind = "0.0.0.0:8002"
workers = 3
worker_class = "gevent"
worker_connections = 1000
timeout = 90
# Access log - records incoming HTTP requests
accesslog = "/var/log/cyberpolygon.access.log"
# Error log - records Gunicorn server goings-on
errorlog = "/var/log/cyberpolygon.log"
# Whether to send Django output to the error log
capture_output = True
# How verbose the Gunicorn error logs should be
loglevel = "info"

# Путь к файлу для хранения маппинга PID -> worker_id
WORKER_MAPPING_FILE = "/tmp/gunicorn_worker_mapping.json"
WORKER_MAPPING_LOCK_FILE = "/tmp/gunicorn_worker_mapping.lock"


def _is_process_alive(pid):
    """Проверяет, жив ли процесс с указанным PID"""
    try:
        # Отправляем сигнал 0 - не убивает процесс, только проверяет существование
        os.kill(pid, 0)
        return True
    except OSError as e:
        if e.errno == errno.ESRCH:  # No such process
            return False
        elif e.errno == errno.EPERM:  # Permission denied (процесс существует, но нет прав)
            return True
        else:
            # Другие ошибки - считаем что процесс жив
            return True


def _get_worker_mapping():
    """Читает маппинг PID -> worker_id из файла с блокировкой"""
    mapping = {}
    if os.path.exists(WORKER_MAPPING_FILE):
        try:
            with open(WORKER_MAPPING_FILE, 'r') as f:
                mapping = json.load(f)
        except (json.JSONDecodeError, IOError):
            mapping = {}
    
    # Очищаем "мертвые" записи
    cleaned_mapping = {}
    for pid_str, worker_id in mapping.items():
        pid = int(pid_str)
        if _is_process_alive(pid):
            cleaned_mapping[pid_str] = worker_id
    
    return cleaned_mapping


def _save_worker_mapping(mapping):
    """Сохраняет маппинг PID -> worker_id в файл"""
    with open(WORKER_MAPPING_FILE, 'w') as f:
        json.dump(mapping, f)


def _acquire_worker_id(worker_pid):
    """
    Получает или назначает worker_id для воркера с указанным PID.
    Использует файловую блокировку для синхронизации между процессами.
    Возвращает worker_id от 1 до workers.
    """
    lock_file = None
    try:
        # Открываем файл блокировки
        lock_file = open(WORKER_MAPPING_LOCK_FILE, 'w')
        
        # Получаем эксклюзивную блокировку (блокирующая)
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        
        # Читаем текущий маппинг
        mapping = _get_worker_mapping()
        pid_str = str(worker_pid)
        
        # Проверяем, есть ли уже запись для этого PID
        if pid_str in mapping:
            worker_id = mapping[pid_str]
        else:
            # Ищем свободный слот (1, 2, 3, ...)
            used_ids = set(int(v) for v in mapping.values())
            worker_id = None
            
            for candidate_id in range(1, workers + 1):
                if candidate_id not in used_ids:
                    worker_id = candidate_id
                    break
            
            # Если все слоты заняты, используем следующий доступный
            # (это может произойти если воркеры перезапускаются очень быстро)
            if worker_id is None:
                # Находим минимальный ID, который можно переиспользовать
                # (берем первый занятый, если все заняты)
                worker_id = 1
            
            # Сохраняем маппинг
            mapping[pid_str] = worker_id
            _save_worker_mapping(mapping)
        
        return worker_id
        
    except Exception as e:
        # В случае ошибки возвращаем дефолтное значение
        # Логируем ошибку, но не падаем
        import sys
        print(f"Error acquiring worker ID: {e}", file=sys.stderr)
        return 1
    finally:
        if lock_file:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                lock_file.close()
            except:
                pass


def _release_worker_id(worker_pid):
    """Освобождает worker_id для воркера с указанным PID"""
    lock_file = None
    try:
        lock_file = open(WORKER_MAPPING_LOCK_FILE, 'w')
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        
        mapping = _get_worker_mapping()
        pid_str = str(worker_pid)
        
        if pid_str in mapping:
            del mapping[pid_str]
            _save_worker_mapping(mapping)
    except Exception as e:
        import sys
        print(f"Error releasing worker ID: {e}", file=sys.stderr)
    finally:
        if lock_file:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                lock_file.close()
            except:
                pass


def post_fork(server, worker):
    """
    Устанавливает переменную окружения GUNICORN_WORKER_ID для каждого воркера.
    Номер воркера начинается с 1 (1, 2, 3, ...) и стабилен даже при перезапусках.
    """
    worker_pid = worker.pid
    worker_id = _acquire_worker_id(worker_pid)
    
    os.environ['GUNICORN_WORKER_ID'] = str(worker_id)
    os.environ['GUNICORN_WORKER_INDEX'] = str(worker_id - 1)  # 0-based для совместимости


def worker_exit(server, worker):
    """
    Вызывается при выходе воркера. Освобождает worker_id.
    """
    worker_pid = worker.pid
    _release_worker_id(worker_pid)