import threading
import time
import unittest
from unittest.mock import patch, MagicMock

from django.test import TestCase
from interface.pnet_session_manager import (
    PNetSessionManager, 
    get_admin_pnet_session, 
    reset_admin_pnet_session, 
    ensure_admin_pnet_session
)


class GlobalPNetSessionTest(TestCase):
    """Тесты для глобальной административной PNet сессии"""

    def setUp(self):
        """Настройка тестов"""
        # Сбрасываем глобальную сессию перед каждым тестом
        reset_admin_pnet_session()

    def tearDown(self):
        """Очистка после тестов"""
        # Сбрасываем глобальную сессию после каждого теста
        reset_admin_pnet_session()

    @patch('interface.models.get_pnet_url')
    @patch('interface.models.pf_login')
    def test_get_admin_pnet_session_creation(self, mock_pf_login, mock_get_pnet_url):
        """Тест создания глобальной сессии"""
        # Мокаем внешние зависимости
        mock_get_pnet_url.return_value = "http://test-pnet.com"
        mock_pf_login.return_value = ("test_cookie", "test_xsrf")

        # Получаем сессию
        session1 = get_admin_pnet_session()
        session2 = get_admin_pnet_session()

        # Проверяем, что возвращается один и тот же экземпляр
        self.assertIs(session1, session2)
        self.assertIsInstance(session1, PNetSessionManager)

    @patch('interface.pnet_session_manager.get_pnet_url')
    @patch('interface.pnet_session_manager.pf_login')
    def test_ensure_admin_pnet_session_auto_login(self, mock_pf_login, mock_get_pnet_url):
        """Тест автоматического логина в глобальной сессии"""
        # Мокаем внешние зависимости
        mock_get_pnet_url.return_value = "http://test-pnet.com"
        mock_pf_login.return_value = ("test_cookie", "test_xsrf")

        # Обеспечиваем готовность сессии
        session = ensure_admin_pnet_session()

        # Проверяем, что логин был выполнен
        mock_pf_login.assert_called_once()
        
        # Проверяем, что сессия аутентифицирована
        try:
            session_data = session.session_data
            self.assertEqual(session_data[0], "http://test-pnet.com")
            self.assertEqual(session_data[1], "test_cookie")
            self.assertEqual(session_data[2], "test_xsrf")
        except RuntimeError:
            self.fail("Сессия должна быть аутентифицирована")

    @patch('interface.pnet_session_manager.get_pnet_url')
    @patch('interface.pnet_session_manager.pf_login')
    def test_ensure_admin_pnet_session_reuse(self, mock_pf_login, mock_get_pnet_url):
        """Тест повторного использования уже аутентифицированной сессии"""
        # Мокаем внешние зависимости
        mock_get_pnet_url.return_value = "http://test-pnet.com"
        mock_pf_login.return_value = ("test_cookie", "test_xsrf")

        # Первый вызов - должен выполнить логин
        session1 = ensure_admin_pnet_session()
        self.assertEqual(mock_pf_login.call_count, 1)

        # Второй вызов - должен переиспользовать существующую сессию
        session2 = ensure_admin_pnet_session()
        self.assertEqual(mock_pf_login.call_count, 1)  # Логин не должен вызываться повторно
        
        # Проверяем, что это один и тот же экземпляр
        self.assertIs(session1, session2)

    @patch('interface.pnet_session_manager.get_pnet_url')
    @patch('interface.pnet_session_manager.pf_login')
    @patch('interface.pnet_session_manager.logout')
    def test_reset_admin_pnet_session(self, mock_logout, mock_pf_login, mock_get_pnet_url):
        """Тест сброса глобальной сессии"""
        # Мокаем внешние зависимости
        mock_get_pnet_url.return_value = "http://test-pnet.com"
        mock_pf_login.return_value = ("test_cookie", "test_xsrf")
        mock_logout.return_value = None

        # Создаем сессию
        session1 = ensure_admin_pnet_session()
        self.assertEqual(mock_pf_login.call_count, 1)

        # Сбрасываем сессию
        reset_admin_pnet_session()
        mock_logout.assert_called_once()

        # Создаем новую сессию
        session2 = ensure_admin_pnet_session()
        self.assertEqual(mock_pf_login.call_count, 2)  # Логин должен вызваться снова
        
        # Проверяем, что это разные экземпляры
        self.assertIsNot(session1, session2)

    @patch('interface.pnet_session_manager.get_pnet_url')
    @patch('interface.pnet_session_manager.pf_login')
    def test_concurrent_access_to_global_session(self, mock_pf_login, mock_get_pnet_url):
        """Тест одновременного доступа к глобальной сессии из разных потоков"""
        # Мокаем внешние зависимости
        mock_get_pnet_url.return_value = "http://test-pnet.com"
        mock_pf_login.return_value = ("test_cookie", "test_xsrf")

        # Функция для выполнения в потоке
        def get_session():
            return ensure_admin_pnet_session()

        # Создаем несколько потоков
        threads = []
        results = []
        
        for i in range(5):
            thread = threading.Thread(target=lambda: results.append(get_session()))
            threads.append(thread)

        # Запускаем все потоки одновременно
        for thread in threads:
            thread.start()

        # Ждем завершения всех потоков
        for thread in threads:
            thread.join()

        # Проверяем результаты
        self.assertEqual(len(results), 5)
        
        # Все потоки должны получить один и тот же экземпляр
        first_session = results[0]
        for session in results[1:]:
            self.assertIs(session, first_session)
        
        # Логин должен быть выполнен только один раз
        mock_pf_login.assert_called_once()

    @patch('interface.pnet_session_manager.get_pnet_url')
    @patch('interface.pnet_session_manager.pf_login')
    def test_global_session_thread_safety(self, mock_pf_login, mock_get_pnet_url):
        """Тест thread-safety глобальной сессии при выполнении операций"""
        # Мокаем внешние зависимости
        mock_get_pnet_url.return_value = "http://test-pnet.com"
        mock_pf_login.return_value = ("test_cookie", "test_xsrf")

        # Функция для выполнения операций в потоке
        def perform_operations():
            session = ensure_admin_pnet_session()
            # Имитируем выполнение операций
            session_data = session.session_data
            time.sleep(0.01)  # Небольшая задержка
            return session_data

        # Создаем несколько потоков
        threads = []
        results = []
        
        for i in range(3):
            thread = threading.Thread(target=lambda: results.append(perform_operations()))
            threads.append(thread)

        # Запускаем все потоки одновременно
        for thread in threads:
            thread.start()

        # Ждем завершения всех потоков
        for thread in threads:
            thread.join()

        # Проверяем результаты
        self.assertEqual(len(results), 3)
        
        # Все операции должны завершиться успешно
        for result in results:
            self.assertEqual(result[0], "http://test-pnet.com")
            self.assertEqual(result[1], "test_cookie")
            self.assertEqual(result[2], "test_xsrf")

    def test_reset_nonexistent_session(self):
        """Тест сброса несуществующей сессии"""
        # Сброс несуществующей сессии не должен вызывать ошибок
        try:
            reset_admin_pnet_session()
            # Если мы дошли сюда, значит ошибок не было
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"Сброс несуществующей сессии вызвал ошибку: {e}")


if __name__ == '__main__':
    unittest.main()
