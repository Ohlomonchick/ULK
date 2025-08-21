import threading
import time
import unittest
from unittest.mock import patch, MagicMock

from django.test import TestCase
from interface.pnet_session_manager import PNetSessionManager


class PNetSessionManagerThreadSafetyTest(TestCase):
    """Тесты для проверки thread-safety PNetSessionManager"""

    def setUp(self):
        """Настройка тестов"""
        self.session_manager = PNetSessionManager()

    @patch('interface.pnet_session_manager.get_pnet_url')
    @patch('interface.pnet_session_manager.pf_login')
    def test_concurrent_login_operations(self, mock_pf_login, mock_get_pnet_url):
        """Тест одновременных операций логина из разных потоков"""
        # Мокаем внешние зависимости
        mock_get_pnet_url.return_value = "http://test-pnet.com"
        mock_pf_login.return_value = ("test_cookie", "test_xsrf")

        # Функция для выполнения в потоке
        def login_operation():
            try:
                self.session_manager.login()
                time.sleep(0.01)  # Небольшая задержка для создания race condition
                return True
            except Exception as e:
                return str(e)

        # Создаем несколько потоков
        threads = []
        results = []
        
        for i in range(5):
            thread = threading.Thread(target=lambda: results.append(login_operation()))
            threads.append(thread)

        # Запускаем все потоки одновременно
        for thread in threads:
            thread.start()

        # Ждем завершения всех потоков
        for thread in threads:
            thread.join()

        # Проверяем результаты
        self.assertEqual(len(results), 5)
        self.assertTrue(all(result is True for result in results))
        
        # Проверяем, что pf_login был вызван только один раз
        mock_pf_login.assert_called_once()

    @patch('interface.pnet_session_manager.get_pnet_url')
    @patch('interface.pnet_session_manager.pf_login')
    @patch('interface.pnet_session_manager.logout')
    def test_concurrent_login_logout_operations(self, mock_logout, mock_pf_login, mock_get_pnet_url):
        """Тест одновременных операций логина и логаута"""
        # Мокаем внешние зависимости
        mock_get_pnet_url.return_value = "http://test-pnet.com"
        mock_pf_login.return_value = ("test_cookie", "test_xsrf")
        mock_logout.return_value = None

        # Функции для выполнения в потоках
        def login_operation():
            try:
                self.session_manager.login()
                return "login_success"
            except Exception as e:
                return f"login_error: {e}"

        def logout_operation():
            try:
                self.session_manager.logout()
                return "logout_success"
            except Exception as e:
                return f"logout_error: {e}"

        # Создаем потоки для логина и логаута
        login_threads = [threading.Thread(target=lambda: results.append(login_operation())) 
                        for _ in range(3)]
        logout_threads = [threading.Thread(target=lambda: results.append(logout_operation())) 
                         for _ in range(2)]

        results = []
        all_threads = login_threads + logout_threads

        # Запускаем все потоки одновременно
        for thread in all_threads:
            thread.start()

        # Ждем завершения всех потоков
        for thread in all_threads:
            thread.join()

        # Проверяем, что все операции завершились успешно
        self.assertEqual(len(results), 5)
        self.assertTrue(all("success" in result for result in results))

    def test_session_data_thread_safety(self):
        """Тест thread-safety для session_data property"""
        # Функция для чтения session_data
        def read_session_data():
            try:
                return self.session_manager.session_data
            except RuntimeError:
                return "not_authenticated"

        # Создаем потоки для чтения session_data
        threads = []
        results = []
        
        for i in range(10):
            thread = threading.Thread(target=lambda: results.append(read_session_data()))
            threads.append(thread)

        # Запускаем все потоки одновременно
        for thread in threads:
            thread.start()

        # Ждем завершения всех потоков
        for thread in threads:
            thread.join()

        # Проверяем, что все потоки получили одинаковый результат
        self.assertEqual(len(results), 10)
        self.assertTrue(all(result == "not_authenticated" for result in results))

    @patch('interface.pnet_session_manager.get_pnet_url')
    @patch('interface.pnet_session_manager.pf_login')
    def test_context_manager_thread_safety(self, mock_pf_login, mock_get_pnet_url):
        """Тест thread-safety для контекстного менеджера"""
        # Мокаем внешние зависимости
        mock_get_pnet_url.return_value = "http://test-pnet.com"
        mock_pf_login.return_value = ("test_cookie", "test_xsrf")

        # Функция для использования контекстного менеджера
        def use_context_manager():
            try:
                with PNetSessionManager() as session:
                    time.sleep(0.01)  # Имитируем работу с сессией
                    return "context_success"
            except Exception as e:
                return f"context_error: {e}"

        # Создаем несколько потоков
        threads = []
        results = []
        
        for i in range(5):
            thread = threading.Thread(target=lambda: results.append(use_context_manager()))
            threads.append(thread)

        # Запускаем все потоки одновременно
        for thread in threads:
            thread.start()

        # Ждем завершения всех потоков
        for thread in threads:
            thread.join()

        # Проверяем результаты
        self.assertEqual(len(results), 5)
        self.assertTrue(all(result == "context_success" for result in results))


if __name__ == '__main__':
    unittest.main()
