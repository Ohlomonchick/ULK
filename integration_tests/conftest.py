"""
Общие фикстуры для интеграционных тестов.
"""
import pytest
import subprocess
import signal
import os
import socket
import time
from pathlib import Path


def find_free_port():
    """Находит свободный порт для тестов"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


@pytest.fixture(scope="session")
def test_port():
    """
    Генерирует уникальный порт для тестов на уровне сессии.
    Используется для изоляции тестов друг от друга.
    """
    return find_free_port()


@pytest.fixture
def cleanup_processes():
    """
    Фикстура для отслеживания и очистки процессов после теста.
    
    Использование:
        def test_something(cleanup_processes):
            process = subprocess.Popen(...)
            cleanup_processes.append(process.pid)
    """
    pids = []
    yield pids
    
    # Очистка процессов
    for pid in pids:
        try:
            if _is_process_alive(pid):
                os.kill(pid, signal.SIGTERM)
                # Ждем завершения
                for _ in range(10):
                    if not _is_process_alive(pid):
                        break
                    time.sleep(0.5)
                else:
                    # Если не завершился, убиваем принудительно
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
        except (ProcessLookupError, OSError):
            pass


def _is_process_alive(pid):
    """Проверяет, жив ли процесс"""
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


@pytest.fixture
def temp_mapping_files(tmp_path):
    """
    Создает временные файлы для маппинга воркеров.
    Возвращает пути к файлам маппинга и блокировки.
    """
    mapping_file = tmp_path / "worker_mapping.json"
    lock_file = tmp_path / "worker_mapping.lock"
    
    # Создаем пустые файлы
    mapping_file.touch()
    lock_file.touch()
    
    yield {
        'mapping': str(mapping_file),
        'lock': str(lock_file)
    }
    
    # Очистка (обычно не нужна, так как tmp_path автоматически очищается)
    try:
        if mapping_file.exists():
            mapping_file.unlink()
        if lock_file.exists():
            lock_file.unlink()
    except OSError:
        pass

