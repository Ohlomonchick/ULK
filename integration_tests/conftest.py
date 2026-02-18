"""Общие фикстуры и orchestration для integration_tests."""

from __future__ import annotations

import logging
import os
import signal
import shutil
import socket
import subprocess
import time
from datetime import datetime
from pathlib import Path

import pytest
import requests

# Prevent ImproperlyConfigured during pytest collection when modules
# import Django-dependent packages before fixtures are evaluated.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Cyberpolygon.settings")


PROJECT_ROOT = Path(__file__).resolve().parent.parent
COMPOSE_FILE = PROJECT_ROOT / "integration_tests" / "docker" / "compose.yml"
INTEGRATION_BASE_URL = "http://127.0.0.1:18080"
# Из контейнера web до nginx по имени сервиса (для одного прогона pytest в контейнере)
INTEGRATION_BASE_URL_IN_CONTAINER = "http://nginx"
INTEGRATION_LOGS_DIR = PROJECT_ROOT / "integration_tests" / "logs"
INTEGRATION_RUN_ID = datetime.now().strftime("run_%Y%m%d_%H%M%S")
INTEGRATION_RUN_LOGS_DIR = INTEGRATION_LOGS_DIR / INTEGRATION_RUN_ID
INTEGRATION_ELASTIC_PORT = 19200
INTEGRATION_ELASTIC_URL = f"https://127.0.0.1:{INTEGRATION_ELASTIC_PORT}"
INTEGRATION_ELASTIC_CERTS_DIR = PROJECT_ROOT / "integration_tests" / "docker" / "certs"
INTEGRATION_ELASTIC_CA_RELATIVE_PATH = "integration_tests/docker/certs/ca.crt"


def find_free_port():
    """Находит свободный порт для тестов."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("", 0))
        sock.listen(1)
        return sock.getsockname()[1]


def _docker_compose(*args: str, stream: bool = False) -> subprocess.CompletedProcess:
    command = ["docker", "compose", "-f", str(COMPOSE_FILE), *args]
    if stream:
        return subprocess.run(command, cwd=PROJECT_ROOT, check=False)
    return subprocess.run(command, cwd=PROJECT_ROOT, capture_output=True, text=True, check=False)


def _ensure_pnet_base_dir(pnet_url: str, cookie, base_dir: str) -> None:
    from integration_tests.utils.pnet_dirs import (
        PnetDirectoryProvisionError,
        ensure_directory_path,
    )

    try:
        ensure_directory_path(pnet_url, cookie, base_dir)
    except PnetDirectoryProvisionError as exc:
        raise RuntimeError(f"PNET base directory provisioning failed for '{base_dir}': {exc}") from exc


def _wait_http_ready(url: str, timeout_seconds: int = 420) -> None:
    deadline = time.time() + timeout_seconds
    last_error = ""
    last_status = None
    last_body = ""
    while time.time() < deadline:
        try:
            response = requests.get(url, timeout=3)
            last_status = response.status_code
            last_body = (response.text or "")[:300]
            if response.status_code < 500:
                return
        except requests.RequestException as exc:
            last_error = str(exc)
        time.sleep(2)
    raise RuntimeError(
        f"Integration stack is not ready: {url}. "
        f"Last status: {last_status}. Last body: {last_body}. Last error: {last_error}"
    )


def _docker_mount_path(path: Path) -> str:
    return path.resolve().as_posix()


def _ensure_elastic_cert_permissions() -> None:
    certs_dir = INTEGRATION_ELASTIC_CERTS_DIR
    ca_dir = certs_dir / "ca"
    files_with_modes = {
        certs_dir / "ca.crt": 0o644,
        certs_dir / "elasticsearch.crt": 0o644,
        certs_dir / "elasticsearch.key": 0o644,
        certs_dir / "ca.p12": 0o644,
        certs_dir / "elasticsearch.p12": 0o644,
        ca_dir / "ca.crt": 0o644,
    }

    for directory in (certs_dir, ca_dir):
        if directory.exists():
            try:
                directory.chmod(0o755)
            except OSError:
                # Best effort on non-POSIX filesystems (e.g. Windows hosts).
                pass

    for file_path, mode in files_with_modes.items():
        if not file_path.exists():
            continue
        try:
            file_path.chmod(mode)
        except OSError:
            # Best effort on non-POSIX filesystems (e.g. Windows hosts).
            pass

    # Also normalize permissions from inside a Linux container (important for Docker bind mounts).
    certs_volume = f"{_docker_mount_path(certs_dir)}:/certs"
    chmod_in_container = [
        "docker",
        "run",
        "--rm",
        "-v",
        certs_volume,
        "alpine:3.20",
        "sh",
        "-lc",
        (
            "mkdir -p /certs/ca && "
            "chmod 755 /certs /certs/ca 2>/dev/null || true; "
            "chmod 644 /certs/*.crt /certs/*.key /certs/*.p12 /certs/ca/*.crt 2>/dev/null || true"
        ),
    ]
    subprocess.run(chmod_in_container, cwd=PROJECT_ROOT, capture_output=True, text=True, check=False)


def _ensure_elastic_certs() -> None:
    required_files = [
        INTEGRATION_ELASTIC_CERTS_DIR / "ca.crt",
        INTEGRATION_ELASTIC_CERTS_DIR / "elasticsearch.crt",
        INTEGRATION_ELASTIC_CERTS_DIR / "elasticsearch.key",
    ]
    if all(path.exists() for path in required_files):
        _ensure_elastic_cert_permissions()
        return

    INTEGRATION_ELASTIC_CERTS_DIR.mkdir(parents=True, exist_ok=True)
    certs_volume = f"{_docker_mount_path(INTEGRATION_ELASTIC_CERTS_DIR)}:/certs"
    es_image = "docker.elastic.co/elasticsearch/elasticsearch:9.1.1"

    certutil_ca = [
        "docker",
        "run",
        "--rm",
        "-v",
        certs_volume,
        es_image,
        "/usr/share/elasticsearch/bin/elasticsearch-certutil",
        "ca",
        "--out",
        "/certs/ca.p12",
        "--pass",
        "",
    ]
    certutil_node = [
        "docker",
        "run",
        "--rm",
        "-v",
        certs_volume,
        es_image,
        "/usr/share/elasticsearch/bin/elasticsearch-certutil",
        "cert",
        "--ca",
        "/certs/ca.p12",
        "--ca-pass",
        "",
        "--out",
        "/certs/elasticsearch.p12",
        "--pass",
        "",
        "--dns",
        "localhost",
        "--dns",
        "elasticsearch",
        "--ip",
        "127.0.0.1",
    ]
    to_ca_crt = [
        "docker",
        "run",
        "--rm",
        "-v",
        certs_volume,
        "alpine/openssl",
        "pkcs12",
        "-in",
        "/certs/ca.p12",
        "-out",
        "/certs/ca.crt",
        "-nokeys",
        "-clcerts",
        "-passin",
        "pass:",
    ]
    to_es_crt = [
        "docker",
        "run",
        "--rm",
        "-v",
        certs_volume,
        "alpine/openssl",
        "pkcs12",
        "-in",
        "/certs/elasticsearch.p12",
        "-out",
        "/certs/elasticsearch.crt",
        "-nokeys",
        "-clcerts",
        "-passin",
        "pass:",
    ]
    to_es_key = [
        "docker",
        "run",
        "--rm",
        "-v",
        certs_volume,
        "alpine/openssl",
        "pkcs12",
        "-in",
        "/certs/elasticsearch.p12",
        "-out",
        "/certs/elasticsearch.key",
        "-nocerts",
        "-nodes",
        "-passin",
        "pass:",
    ]

    for command in (certutil_ca, certutil_node, to_ca_crt, to_es_crt, to_es_key):
        completed = subprocess.run(command, cwd=PROJECT_ROOT, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            raise RuntimeError(
                f"Failed to generate Elasticsearch certificates. Command: {' '.join(command)}. "
                f"Stdout: {completed.stdout}. Stderr: {completed.stderr}"
            )

    (INTEGRATION_ELASTIC_CERTS_DIR / "ca").mkdir(parents=True, exist_ok=True)
    shutil.copy2(INTEGRATION_ELASTIC_CERTS_DIR / "ca.crt", INTEGRATION_ELASTIC_CERTS_DIR / "ca" / "ca.crt")
    _ensure_elastic_cert_permissions()


def _wait_elasticsearch_ready(url: str, timeout_seconds: int = 300) -> None:
    deadline = time.time() + timeout_seconds
    last_error = ""
    last_status = None
    last_body = ""

    while time.time() < deadline:
        try:
            response = requests.get(
                f"{url}/_cluster/health",
                auth=("elastic", "elastic"),
                verify=False,
                timeout=5,
            )
            last_status = response.status_code
            last_body = (response.text or "")[:300]
            if response.status_code == 200:
                return
        except requests.RequestException as exc:
            last_error = str(exc)
        time.sleep(2)

    raise RuntimeError(
        f"Elasticsearch is not ready: {url}. "
        f"Last status: {last_status}. Last body: {last_body}. Last error: {last_error}"
    )


def _sanitize_nodeid(nodeid: str) -> str:
    # nodeid format: path::test_name[param]
    sanitized = nodeid.replace("::", "__").replace("/", "_").replace("\\", "_")
    for symbol in ["[", "]", ":", " ", "|", "<", ">", "\"", "'"]:
        sanitized = sanitized.replace(symbol, "_")
    return sanitized


def pytest_addoption(parser):
    parser.addoption(
        "--keep-pnet-on-fail",
        action="store_true",
        default=False,
        help="When set, do not delete PNET users/folders/labs and DB seed data after a failed test (for inspection). Cleanup always runs on success.",
    )


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Store test outcome so cleanup_context can skip PNET/DB cleanup on failure when --keep-pnet-on-fail is set."""
    outcome = yield
    rep = outcome.get_result()
    if rep.when == "call":
        item._test_outcome = rep.outcome  # "passed", "failed", "skipped"


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    """Attach a dedicated file logger for each test."""
    INTEGRATION_RUN_LOGS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{_sanitize_nodeid(item.nodeid)}.log"
    log_path = INTEGRATION_RUN_LOGS_DIR / filename

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    _prev_level = root_logger.level
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    item._integration_log_handler = file_handler
    item._integration_log_path = str(log_path)
    item._integration_log_prev_level = _prev_level
    root_logger.info("Started test log file: %s", log_path)


@pytest.hookimpl(trylast=True)
def pytest_runtest_teardown(item, nextitem):
    """Detach per-test file logger and close descriptor."""
    file_handler = getattr(item, "_integration_log_handler", None)
    log_path = getattr(item, "_integration_log_path", "unknown")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fallback_line = f"{timestamp} [INFO] root: Finished test log file: {log_path}\n"

    if file_handler is not None:
        root_logger = logging.getLogger()
        root_logger.info("Finished test log file: %s", log_path)
        root_logger.removeHandler(file_handler)
        file_handler.close()
        prev_level = getattr(item, "_integration_log_prev_level", logging.WARNING)
        root_logger.setLevel(prev_level)

    # Safety net: append explicit finish marker even if logging pipeline was interrupted.
    if log_path != "unknown":
        try:
            with Path(log_path).open("a", encoding="utf-8") as log_file:
                log_file.write(fallback_line)
        except OSError:
            pass


@pytest.fixture(scope="session")
def test_port():
    """Уникальный порт для тестов уровня сессии."""
    return find_free_port()


@pytest.fixture(scope="session")
def integration_env() -> dict:
    """
    Конфиг для интеграционного прогона.

    Обязательная переменная:
    - PNET_IP
    """
    pnet_ip = os.environ.get("PNET_IP", "").strip()
    if not pnet_ip:
        pytest.skip("PNET_IP is not set. Integration stack requires real PNET.")

    run_id = f"it_{int(time.time())}"
    # Базовый воркспейс для Student в PNET: /Practice Work/Test_Labs.
    # Лабы и папки пользователей — под /Practice Work/Test_Labs/IT_TestLabs/<run_id>,
    # воркспейс пользователя задаётся относительно STUDENT_WORKSPACE: /IT_TestLabs/<run_id>/<username>.
    student_workspace = "Practice Work/Test_Labs"
    pnet_base_dir = f"/Practice Work/Test_Labs/IT_TestLabs/{run_id}"

    env = {
        "PNET_IP": pnet_ip,
        "PNET_URL": f"http://{pnet_ip}",
        "PNET_BASE_DIR": pnet_base_dir,
        "STUDENT_WORKSPACE": student_workspace,
        "WEB_URL": "http://127.0.0.1:18080",
        "USE_POSTGRES": "yes",
        "DB_HOST": "127.0.0.1",
        "DB_PORT": "55431",
        "DB_NAME": "cyberpolygon",
        "DB_USER": "postgres",
        "DB_PASSWORD": "postgres",
        "PROD": "False",
        "DJANGO_SETTINGS_MODULE": "Cyberpolygon.settings",
        "INTEGRATION_RUN_ID": INTEGRATION_RUN_ID,
    }
    return env


@pytest.fixture(scope="session")
def integration_stack(integration_env):
    """
    Поднимает Docker stack: postgres + web + nginx (или только ждёт готовности,
    если стек уже поднят снаружи — INTEGRATION_STACK_EXTERNAL=1, см. run_e2e.ps1).
    """
    os.environ.update(
        {
            "PNET_IP": integration_env["PNET_IP"],
            "PNET_URL": integration_env["PNET_URL"],
            "PNET_BASE_DIR": integration_env["PNET_BASE_DIR"],
            "STUDENT_WORKSPACE": integration_env["STUDENT_WORKSPACE"],
        }
    )
    _ensure_elastic_certs()

    stack_external = os.environ.get("INTEGRATION_STACK_EXTERNAL") == "1"

    if not stack_external:
        print("[integration] docker compose down -v")
        down_before = _docker_compose("down", "-v", stream=True)
        if down_before.returncode != 0:
            pass

        print("[integration] docker compose up -d")
        up = _docker_compose("up", "-d", stream=True)
        if up.returncode != 0:
            logs = _docker_compose("logs", "--no-color", stream=True)
            raise RuntimeError(
                f"docker compose up failed with exit code: {up.returncode}; logs exit code: {logs.returncode}"
            )

    base_url = (
        INTEGRATION_BASE_URL_IN_CONTAINER
        if os.environ.get("INTEGRATION_GUNICORN") == "1"
        else INTEGRATION_BASE_URL
    )
    print(f"[integration] waiting http ready: {base_url}")
    _wait_http_ready(base_url)
    print(f"[integration] waiting elastic ready: {INTEGRATION_ELASTIC_URL}")
    _wait_elasticsearch_ready(INTEGRATION_ELASTIC_URL)
    print("[integration] stack is ready")

    yield {
        "base_url": base_url,
        "compose_file": str(COMPOSE_FILE),
    }

    if not stack_external:
        print("[integration] docker compose down -v")
        down = _docker_compose("down", "-v", stream=True)
        if down.returncode != 0:
            raise RuntimeError(f"docker compose down failed with exit code: {down.returncode}")


@pytest.fixture(scope="session")
def django_ready(integration_env, integration_stack):
    """
    Инициализирует Django ORM для seed/assert операций из pytest процесса.
    """
    os.environ.update(integration_env)

    import django

    django.setup()
    from dynamic_config.utils import set_config

    # Make Elasticsearch config deterministic for integration tests.
    set_config("ELASTIC_URL", INTEGRATION_ELASTIC_URL)
    set_config("ELASTIC_USERNAME", "elastic")
    set_config("ELASTIC_PASSWORD", "elastic")
    set_config("ELASTIC_USE_HTTPS", "true")
    set_config("ELASTIC_CA_CERT_PATH", INTEGRATION_ELASTIC_CA_RELATIVE_PATH)

    yield


@pytest.fixture
def reattach_integration_log_file(request, django_ready):
    """
    Re-attach the per-test file handler to the root logger after Django has applied
    LOGGING config (which replaces root handlers with console only). Ensures
    all test-phase logs appear in the test log file.
    """
    root_logger = logging.getLogger()
    handler = getattr(request.node, "_integration_log_handler", None)
    if handler is not None and handler not in root_logger.handlers:
        root_logger.addHandler(handler)
        root_logger.setLevel(logging.DEBUG)


@pytest.fixture
def pnet_admin_session(integration_env, django_ready):
    """Административная сессия PNET для проверок и cleanup."""
    os.environ.update(integration_env)
    from integration_tests.utils.pnet_cleanup import login_admin_to_pnet

    pnet_url = f"http://{integration_env['PNET_IP']}"
    cookie, xsrf = login_admin_to_pnet(pnet_url)
    _ensure_pnet_base_dir(pnet_url, cookie, integration_env["PNET_BASE_DIR"])
    return {"pnet_url": pnet_url, "cookie": cookie, "xsrf": xsrf}


@pytest.fixture
def cleanup_context(request, integration_env, pnet_admin_session, reattach_integration_log_file):
    """
    Сборщик side-effects для теста.

    По умолчанию в teardown всегда выполняется очистка PNET (лабы, пользователи, папки)
    и БД (seed-сущности по префиксу). Если передан --keep-pnet-on-fail и тест упал,
    очистка не выполняется (артефакты остаются для разбора).
    """
    context = {
        "users": set(),
        "folders": set(),
        "labs": [],
        "prefixes_for_db": set(),
    }
    yield context

    keep_on_fail = request.config.getoption("keep_pnet_on_fail", default=False)
    test_outcome = getattr(request.node, "_test_outcome", "passed")
    skip_cleanup = keep_on_fail and test_outcome == "failed"

    if skip_cleanup:
        logging.getLogger(__name__).info(
            "Skipping PNET/DB cleanup for failed test (--keep-pnet-on-fail); artifacts left for inspection."
        )
        return

    try:
        from integration_tests.utils.db_seed import cleanup_seeded_entities
        from integration_tests.utils.pnet_cleanup import (
            login_admin_to_pnet,
            safe_delete_folders,
            safe_delete_labs,
            safe_delete_users,
        )

        pnet_url = pnet_admin_session["pnet_url"]
        # Свежая сессия в teardown: cookie к концу теста мог истечь
        cookie, xsrf = login_admin_to_pnet(pnet_url)
        base_dir = integration_env["PNET_BASE_DIR"].rstrip("/")

        safe_delete_labs(pnet_url, cookie, xsrf, integration_env["PNET_BASE_DIR"], context["labs"])

        # Папки воркспейса пользователей (base_dir/<pnet_login>) создаются формой при создании пользователя,
        # но в cleanup_context["folders"] их добавляет только test_user_lifecycle; для остальных тестов
        # добавляем их здесь по списку users, иначе директории остаются в PNET.
        user_folders = {f"{base_dir}/{u}" for u in context["users"]}
        all_folders = set(context["folders"]) | user_folders
        safe_delete_folders(pnet_url, cookie, all_folders)

        safe_delete_users(pnet_url, cookie, xsrf, context["users"])
        for prefix in context["prefixes_for_db"]:
            cleanup_seeded_entities(prefix)
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).warning(
            "Cleanup teardown swallowed exception to avoid ERROR in pytest: %s", exc
        )


@pytest.fixture
def cleanup_processes():
    """
    Фикстура для отслеживания и очистки локальных процессов после теста.
    """
    pids = []
    yield pids

    for pid in pids:
        try:
            if _is_process_alive(pid):
                os.kill(pid, signal.SIGTERM)
                for _ in range(10):
                    if not _is_process_alive(pid):
                        break
                    time.sleep(0.5)
                else:
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
        except (ProcessLookupError, OSError):
            pass


def _is_process_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


@pytest.fixture
def temp_mapping_files(tmp_path):
    """Создает временные файлы маппинга воркеров gunicorn."""
    mapping_file = tmp_path / "worker_mapping.json"
    lock_file = tmp_path / "worker_mapping.lock"

    mapping_file.touch()
    lock_file.touch()

    yield {"mapping": str(mapping_file), "lock": str(lock_file)}

    try:
        if mapping_file.exists():
            mapping_file.unlink()
        if lock_file.exists():
            lock_file.unlink()
    except OSError:
        pass

