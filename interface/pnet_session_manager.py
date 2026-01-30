import logging
import threading
from functools import wraps

from interface.eveFunctions import change_user_password, create_directory, create_user, pf_login, create_lab, logout, create_all_lab_nodes_and_connectors, \
    delete_lab_with_session_destroy, change_user_workspace
from interface.config import get_pnet_url, get_pnet_base_dir, cache_for_minutes
from interface.utils import get_gunicorn_worker_id
from dynamic_config.utils import get_worker_credentials

logger = logging.getLogger(__name__)


@cache_for_minutes(5)
def _get_cached_worker_credentials(worker_id):
    """Получить credentials для воркера с кэшированием на 5 минут (модульный уровень)"""
    return get_worker_credentials(worker_id)


def require_pnet_url(func):
    """
    Декоратор для методов класса PNetSessionManager.
    Проверяет, что self._url не пустой перед выполнением метода.
    Если URL пустой, метод не выполняется и возвращается None.
    """
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if self._url == "":
            return None
        return func(self, *args, **kwargs)
    return wrapper


def exclusive_session_lock(func):
    """
    Декоратор для методов класса PNetSessionManager.
    Обеспечивает эксклюзивное выполнение методов с этим декоратором.

    Все методы с этим декоратором будут выполняться последовательно:
    - Ни одна другая функция с таким же декоратором не начнёт выполняться,
      пока не закончится выполнение текущей функции
    - Сама функция будет ждать, пока завершатся другие функции с таким же декоратором

    Использует блокировку на уровне экземпляра (self._exclusive_lock).
    """
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        # Выполняем функцию с эксклюзивной блокировкой
        with self._exclusive_lock:
            return func(self, *args, **kwargs)
    return wrapper


# Глобальная административная сессия PNet
ADMIN_PNET_SESSION = None
ADMIN_SESSION_LOCK = threading.Lock()


def get_admin_pnet_session():
    """
    Получение глобальной административной сессии PNet.
    Thread-safe создание и возврат сессии.
    """
    global ADMIN_PNET_SESSION

    with ADMIN_SESSION_LOCK:
        if ADMIN_PNET_SESSION is None:
            ADMIN_PNET_SESSION = PNetSessionManager()
            logger.info("Создана глобальная административная PNet сессия")

        return ADMIN_PNET_SESSION


def reset_admin_pnet_session():
    """
    Сброс глобальной административной сессии PNet.
    Используется для принудительного пересоздания сессии.
    """
    global ADMIN_PNET_SESSION

    with ADMIN_SESSION_LOCK:
        if ADMIN_PNET_SESSION is not None:
            try:
                ADMIN_PNET_SESSION.logout()
                logger.info("Закрыта глобальная административная PNet сессия")
            except Exception as e:
                logger.warning(f"Ошибка при закрытии глобальной сессии: {e}")
            finally:
                ADMIN_PNET_SESSION = None


def ensure_admin_pnet_session():
    """
    Обеспечение готовности глобальной административной сессии.
    Автоматически выполняет логин если сессия не аутентифицирована.
    """
    session = get_admin_pnet_session()
    session._url = get_pnet_url()
    if not session._url:
        return session

    # Проверяем состояние сессии без блокировки (внутренняя блокировка уже есть)
    try:
        session.session_data
        return session
    except RuntimeError:
        # Сессия не аутентифицирована, выполняем логин
        session.login()
        return session


def execute_pnet_operation_if_needed(lab, operation):
    """
    Выполняет операцию с PNet сессией только если лабораторная работа использует платформу PN.
    """
    if lab.get_platform() == "PN" or lab.get_platform() == "CMD":
        session_manager = ensure_admin_pnet_session()
        operation(session_manager)


def with_pnet_session_if_needed(lab, operation):
    """
    Выполняет операцию с PNet сессией только если лабораторная работа использует платформу PN.
    """
    if lab.get_platform() == "PN" or lab.get_platform() == "CMD":
        session_manager = ensure_admin_pnet_session()
        with session_manager:
            operation()
    else:
        operation()


class PNetSessionManager:
    """
    Менеджер для управления PNet сессиями.
    Позволяет переиспользовать одну сессию для множественных операций.

    Thread-safety:
    - Все операции с состоянием аутентификации защищены блокировкой
    - Экземпляр класса может безопасно использоваться в многопоточной среде
    - Каждый экземпляр имеет собственную блокировку
    - Рекомендуется создавать отдельный экземпляр для каждого потока
      или использовать в контекстном менеджере with_pnet_session_if_needed для автоматического управления
    """

    def __init__(self, do_logout=False):
        self._session = None
        self._url = None
        self._cookie = None
        self._xsrf = None
        self._is_authenticated = False
        self._pnet_login = None  # Логин текущей сессии
        self._lock = threading.Lock()  # Блокировка для thread-safety
        self._exclusive_lock = threading.Lock()  # Блокировка для эксклюзивного выполнения методов
        self._do_logout = do_logout

    def __enter__(self):
        """Контекстный менеджер для автоматического логина/логаута"""
        self.login()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Автоматический логаут при выходе из контекста"""
        if self._do_logout:
            self.logout()

    def login(self, url=None):
        """Логин в PNet если еще не залогинены. url — опциональный URL (иначе берётся из настроек)."""
        with self._lock:  # Атомарная проверка и установка флага
            self._url = url if url is not None else get_pnet_url()
            if not self._url:
                raise ValueError("PNet URL не настроен")

            # Пытаемся получить credentials для воркера
            worker_id = get_gunicorn_worker_id()
            login = 'pnet_scripts'
            password = 'eve'

            if worker_id is not None:
                worker_creds = _get_cached_worker_credentials(worker_id)
                if worker_creds:
                    login = worker_creds.get('username')
                    password = worker_creds.get('password')
                    logger.debug(f"Используются credentials воркера {worker_id}: {login}")
                else:
                    logger.debug(f"Credentials для воркера {worker_id} не найдены, используется fallback pnet_scripts")
            else:
                logger.debug("Gunicorn worker ID не определен, используется fallback pnet_scripts")

            self._cookie, self._xsrf = pf_login(self._url, login, password)
            self._pnet_login = login
            self._is_authenticated = True
            logger.debug(f"PNet сессия создана для пользователя {login}")

    def logout(self):
        """Логаут из PNet"""
        with self._lock:  # Атомарная проверка и сброс флага
            if self._is_authenticated and self._url:
                try:
                    logout(self._url)
                    logger.debug("PNet сессия закрыта")
                except Exception as e:
                    logger.warning(f"Ошибка при логауте из PNet: {e}")
                finally:
                    self._is_authenticated = False
                    self._cookie = None
                    self._xsrf = None
                    self._pnet_login = None

    @property
    def session_data(self):
        """Возвращает данные сессии для использования в операциях"""
        with self._lock:  # Атомарная проверка состояния
            if self._url == "":
                return None, None, None
            if not self._is_authenticated:
                raise RuntimeError("Сессия не активна. Вызовите login() сначала")
            return self._url, self._cookie, self._xsrf

    @property
    def pnet_login(self):
        """Возвращает логин текущей PNet сессии"""
        with self._lock:
            return self._pnet_login

    @require_pnet_url
    def create_lab_for_user(self, lab_name, username):
        """Создание лаборатории для пользователя"""
        url, cookie, xsrf = self.session_data
        create_lab(url, lab_name, "", get_pnet_base_dir(), cookie, xsrf, username)

    @exclusive_session_lock
    @require_pnet_url
    def create_lab_nodes_and_connectors(self, lab, lab_name, username, post_nodes_callback=None, usb_device_ids=None):
        """Создание узлов и коннекторов для пользователя"""
        url, cookie, xsrf = self.session_data
        pnet_login = self.pnet_login
        return create_all_lab_nodes_and_connectors(url, lab, get_pnet_base_dir(), lab_name, cookie, xsrf, username, post_nodes_callback, usb_device_ids, pnet_login)

    @require_pnet_url
    def delete_lab_for_team(self, lab_name, team_slug):
        """Удаление лаборатории для команды"""
        url, cookie, xsrf = self.session_data
        delete_lab_with_session_destroy(
            url, lab_name,
            get_pnet_base_dir(), cookie, xsrf, team_slug
        )

    @require_pnet_url
    def delete_lab_for_user(self, lab_name, username):
        """Удаление лаборатории для пользователя"""
        url, cookie, xsrf = self.session_data
        delete_lab_with_session_destroy(
            url, lab_name,
            get_pnet_base_dir(), cookie, xsrf, username
        )

    @require_pnet_url
    def change_user_workspace(self, username, workspace_path):
        """Изменение рабочего пространства пользователя"""
        url, cookie, xsrf = self.session_data
        change_user_workspace(url, cookie, xsrf, username, workspace_path)

    @require_pnet_url
    def change_user_password(self, username, password):
        """Изменение пароля пользователя. Возвращает результат от API или None, если пользователь не найден."""
        url, cookie, xsrf = self.session_data
        return change_user_password(url, cookie, xsrf, username, password)

    @require_pnet_url
    def create_directory(self, path, dir_name):
        """Создание директории"""
        url, cookie, xsrf = self.session_data
        create_directory(url, path, dir_name, cookie)

    @require_pnet_url
    def create_user(self, username, password):
        """Создание пользователя"""
        url, cookie, xsrf = self.session_data
        create_user(url, username, password, '1', cookie)
