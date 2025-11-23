# Интеграционные тесты

Этот каталог содержит интеграционные тесты для проверки взаимодействия различных компонентов системы.

## Структура

```
integration_tests/
├── README.md                    # Этот файл
├── __init__.py
├── gunicorn/                    # Тесты для Gunicorn
│   ├── __init__.py
│   └── test_gunicorn_conf.py
└── conftest.py                  # Общие фикстуры pytest
```

## Рекомендуемые библиотеки

### Для управления процессами

1. **pytest-xprocess** - управление внешними процессами
   ```bash
   pip install pytest-xprocess
   ```

2. **pytest-timeout** - автоматические таймауты для тестов
   ```bash
   pip install pytest-timeout
   ```

3. **psutil** - более удобная работа с процессами
   ```bash
   pip install psutil
   ```

### Для HTTP-тестирования

1. **httpx** - современная альтернатива requests с async поддержкой
   ```bash
   pip install httpx
   ```

2. **responses** - мокирование HTTP-запросов
   ```bash
   pip install responses
   ```

### Для Docker/контейнеров

1. **pytest-docker** - управление Docker-контейнерами в тестах
   ```bash
   pip install pytest-docker
   ```

2. **testcontainers-python** - библиотека для тестовых контейнеров
   ```bash
   pip install testcontainers
   ```

## Best Practices

### 1. Использование фикстур для процессов

Создайте `integration_tests/conftest.py` с переиспользуемыми фикстурами:

```python
import pytest
import subprocess
import signal
import os
import time
from pathlib import Path

@pytest.fixture(scope="session")
def gunicorn_server_process():
    """Фикстура для запуска Gunicorn сервера на уровне сессии"""
    process = None
    try:
        # Запуск процесса
        process = subprocess.Popen(...)
        yield process
    finally:
        # Гарантированная очистка
        if process:
            process.terminate()
            process.wait(timeout=10)
```

### 2. Использование context managers

```python
from contextlib import contextmanager

@contextmanager
def managed_process(cmd, **kwargs):
    """Context manager для управления процессами"""
    process = subprocess.Popen(cmd, **kwargs)
    try:
        yield process
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=10)
```

### 3. Маркировка тестов

Используйте pytest markers для категоризации:

```python
import pytest

@pytest.mark.integration
@pytest.mark.slow
def test_worker_restart():
    """Тест с маркерами"""
    pass
```

Запуск только интеграционных тестов:
```bash
pytest -m integration
```

### 4. Конфигурация pytest

Создайте `pytest.ini` или `pyproject.toml`:

```ini
[pytest]
markers =
    integration: интеграционные тесты
    slow: медленные тесты (> 5 секунд)
    requires_linux: требует Linux окружения
    requires_docker: требует Docker

testpaths = 
    interface/tests
    integration_tests

timeout = 300
timeout_method = thread
```

### 5. Изоляция тестов

- Используйте уникальные порты для каждого теста
- Очищайте временные файлы в `tearDown`/`finally`
- Используйте временные директории для файлов маппинга

### 6. Логирование и отладка

```python
import logging

logger = logging.getLogger(__name__)

def test_with_logging():
    logger.info("Starting test")
    # ...
    logger.debug("Debug information")
```

Запуск с подробным логированием:
```bash
pytest -v -s --log-cli-level=DEBUG
```

## Пример улучшенной структуры

```python
# integration_tests/conftest.py
import pytest
import subprocess
import signal
import os
from pathlib import Path

@pytest.fixture(scope="session")
def test_port():
    """Генерирует уникальный порт для тестов"""
    import socket
    with socket.socket() as s:
        s.bind(('', 0))
        return s.getsockname()[1]

@pytest.fixture
def cleanup_processes():
    """Фикстура для очистки процессов после теста"""
    pids = []
    yield pids
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
```

## CI/CD интеграция

Добавьте в `.github/workflows/tests.yml` или аналогичный файл:

```yaml
- name: Run integration tests
  run: |
    pytest integration_tests/ -m integration --timeout=600
```

## Дополнительные ресурсы

- [pytest documentation](https://docs.pytest.org/)
- [Testing Django Applications](https://docs.djangoproject.com/en/stable/topics/testing/)
- [pytest-xprocess](https://pytest-xprocess.readthedocs.io/)

