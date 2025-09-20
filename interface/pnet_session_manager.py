import logging
import threading
from functools import wraps

from interface.eveFunctions import pf_login, create_lab, logout, create_all_lab_nodes_and_connectors, \
    delete_lab_with_session_destroy, change_user_workspace
from interface.utils import get_pnet_lab_name
from interface.config import get_pnet_url, get_pnet_base_dir

logger = logging.getLogger(__name__)


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
    
    def __init__(self):
        self._session = None
        self._url = None
        self._cookie = None
        self._xsrf = None
        self._is_authenticated = False
        self._lock = threading.Lock()  # Блокировка для thread-safety
    
    def __enter__(self):
        """Контекстный менеджер для автоматического логина/логаута"""
        self.login()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Автоматический логаут при выходе из контекста"""
        self.logout()
    
    def login(self):
        """Логин в PNet если еще не залогинены"""
        with self._lock:  # Атомарная проверка и установка флага
            if self._is_authenticated:
                return
            
            self._url = get_pnet_url()
            if not self._url:
                raise ValueError("PNet URL не настроен")
            
            Login = 'pnet_scripts'
            Pass = 'eve'
            
            self._cookie, self._xsrf = pf_login(self._url, Login, Pass)
            self._is_authenticated = True
            logger.debug("PNet сессия создана")
    
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
    
    @property
    def session_data(self):
        """Возвращает данные сессии для использования в операциях"""
        with self._lock:  # Атомарная проверка состояния
            if self._url == "":
                return None, None, None
            if not self._is_authenticated:
                raise RuntimeError("Сессия не активна. Вызовите login() сначала")
            return self._url, self._cookie, self._xsrf
    
    @require_pnet_url
    def create_lab_for_user(self, lab, username):
        """Создание лаборатории для пользователя"""
        url, cookie, xsrf = self.session_data
        create_lab(url, get_pnet_lab_name(lab), "", get_pnet_base_dir(), cookie, xsrf, username)
    
    @require_pnet_url
    def create_lab_nodes_and_connectors(self, lab, username):
        """Создание узлов и коннекторов для пользователя"""
        url, cookie, xsrf = self.session_data
        create_all_lab_nodes_and_connectors(url, lab, get_pnet_base_dir(), cookie, xsrf, username)
    
    @require_pnet_url
    def delete_lab_for_team(self, lab, team_slug):
        """Удаление лаборатории для команды"""
        url, cookie, xsrf = self.session_data
        delete_lab_with_session_destroy(
            url, lab.slug + '_' + lab.lab_type.lower(), 
            get_pnet_base_dir(), cookie, xsrf, team_slug
        )

    @require_pnet_url
    def delete_lab_for_user(self, lab, username):
        """Удаление лаборатории для пользователя"""
        url, cookie, xsrf = self.session_data
        delete_lab_with_session_destroy(
            url, lab.slug + '_' + lab.lab_type.lower(), 
            get_pnet_base_dir(), cookie, xsrf, username
        )
    
    @require_pnet_url
    def change_user_workspace(self, username, workspace_path):
        """Изменение рабочего пространства пользователя"""
        url, cookie, xsrf = self.session_data
        change_user_workspace(url, cookie, xsrf, username, workspace_path)
