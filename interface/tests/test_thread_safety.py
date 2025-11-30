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

    @patch('interface.pnet_session_manager.get_pnet_url')
    @patch('interface.pnet_session_manager.pf_login')
    @patch('interface.pnet_session_manager.create_all_lab_nodes_and_connectors')
    def test_exclusive_session_lock_sequential_execution(self, mock_create_nodes, mock_pf_login, mock_get_pnet_url):
        """Тест эксклюзивной блокировки: функции выполняются последовательно"""
        # Мокаем внешние зависимости
        mock_get_pnet_url.return_value = "http://test-pnet.com"
        mock_pf_login.return_value = ("test_cookie", "test_xsrf")
        
        # Создаем список для отслеживания порядка выполнения
        execution_order = []
        execution_lock = threading.Lock()
        
        # Мокаем функцию создания узлов с задержкой
        def mock_create_with_delay(*args, **kwargs):
            with execution_lock:
                execution_order.append(threading.current_thread().ident)
            time.sleep(0.05)  # Задержка для проверки последовательности
            return "success"
        
        mock_create_nodes.side_effect = mock_create_with_delay
        
        # Выполняем логин
        self.session_manager.login()
        
        # Мокаем lab объект
        mock_lab = MagicMock()
        
        # Функция для выполнения в потоке
        def create_nodes_operation(thread_id):
            try:
                result = self.session_manager.create_lab_nodes_and_connectors(
                    mock_lab, f"lab_{thread_id}", f"user_{thread_id}"
                )
                return f"success_{thread_id}"
            except Exception as e:
                return f"error_{thread_id}: {e}"
        
        # Создаем несколько потоков
        threads = []
        results = []
        
        for i in range(5):
            thread = threading.Thread(
                target=lambda tid=i: results.append(create_nodes_operation(tid))
            )
            threads.append(thread)
        
        # Запускаем все потоки одновременно
        for thread in threads:
            thread.start()
        
        # Ждем завершения всех потоков
        for thread in threads:
            thread.join()
        
        # Проверяем результаты
        self.assertEqual(len(results), 5)
        self.assertTrue(all("success" in result for result in results))
        
        # Проверяем, что функции выполнялись последовательно
        # (все вызовы mock_create_nodes должны были произойти последовательно)
        self.assertEqual(len(execution_order), 5)

    @patch('interface.pnet_session_manager.get_pnet_url')
    @patch('interface.pnet_session_manager.pf_login')
    @patch('interface.pnet_session_manager.create_all_lab_nodes_and_connectors')
    def test_exclusive_session_lock_waiting_behavior(self, mock_create_nodes, mock_pf_login, mock_get_pnet_url):
        """Тест эксклюзивной блокировки: функция ждет завершения других функций"""
        # Мокаем внешние зависимости
        mock_get_pnet_url.return_value = "http://test-pnet.com"
        mock_pf_login.return_value = ("test_cookie", "test_xsrf")
        
        # Счетчик для отслеживания одновременных выполнений
        active_executions = []
        active_lock = threading.Lock()
        
        # Мокаем функцию создания узлов с проверкой одновременности
        def mock_create_with_check(*args, **kwargs):
            thread_id = threading.current_thread().ident
            with active_lock:
                active_executions.append(thread_id)
                current_count = len(active_executions)
            
            # Задержка для имитации работы
            time.sleep(0.1)
            
            with active_lock:
                active_executions.remove(thread_id)
            
            return "success"
        
        mock_create_nodes.side_effect = mock_create_with_check
        
        # Выполняем логин
        self.session_manager.login()
        
        # Мокаем lab объект
        mock_lab = MagicMock()
        
        # Функция для выполнения в потоке
        def create_nodes_operation(thread_id):
            try:
                result = self.session_manager.create_lab_nodes_and_connectors(
                    mock_lab, f"lab_{thread_id}", f"user_{thread_id}"
                )
                return "success"
            except Exception as e:
                return f"error: {e}"
        
        # Создаем несколько потоков
        threads = []
        results = []
        
        for i in range(5):
            thread = threading.Thread(
                target=lambda tid=i: results.append(create_nodes_operation(tid))
            )
            threads.append(thread)
        
        # Запускаем все потоки одновременно
        start_time = time.time()
        for thread in threads:
            thread.start()
        
        # Ждем завершения всех потоков
        for thread in threads:
            thread.join()
        end_time = time.time()
        
        # Проверяем результаты
        self.assertEqual(len(results), 5)
        self.assertTrue(all(result == "success" for result in results))
        
        # Проверяем, что выполнение заняло достаточно времени
        # (если бы выполнялось параллельно, заняло бы ~0.1 сек, последовательно - ~0.5 сек)
        self.assertGreater(end_time - start_time, 0.4)

    @patch('interface.pnet_session_manager.get_pnet_url')
    @patch('interface.pnet_session_manager.pf_login')
    @patch('interface.pnet_session_manager.create_all_lab_nodes_and_connectors')
    def test_exclusive_session_lock_no_concurrent_execution(self, mock_create_nodes, mock_pf_login, mock_get_pnet_url):
        """Тест эксклюзивной блокировки: нет одновременных выполнений"""
        # Мокаем внешние зависимости
        mock_get_pnet_url.return_value = "http://test-pnet.com"
        mock_pf_login.return_value = ("test_cookie", "test_xsrf")
        
        # Счетчик для отслеживания одновременных выполнений
        concurrent_count = []
        concurrent_lock = threading.Lock()
        
        # Мокаем функцию создания узлов с проверкой одновременности
        def mock_create_with_concurrency_check(*args, **kwargs):
            thread_id = threading.current_thread().ident
            with concurrent_lock:
                concurrent_count.append(1)
                current_concurrent = len(concurrent_count)
            
            # Небольшая задержка для проверки
            time.sleep(0.05)
            
            with concurrent_lock:
                concurrent_count.pop()
            
            # Проверяем, что никогда не было больше одного одновременного выполнения
            if current_concurrent > 1:
                raise AssertionError(f"Обнаружено {current_concurrent} одновременных выполнений!")
            
            return "success"
        
        mock_create_nodes.side_effect = mock_create_with_concurrency_check
        
        # Выполняем логин
        self.session_manager.login()
        
        # Мокаем lab объект
        mock_lab = MagicMock()
        
        # Функция для выполнения в потоке
        def create_nodes_operation(thread_id):
            try:
                result = self.session_manager.create_lab_nodes_and_connectors(
                    mock_lab, f"lab_{thread_id}", f"user_{thread_id}"
                )
                return "success"
            except Exception as e:
                return f"error: {e}"
        
        # Создаем несколько потоков
        threads = []
        results = []
        
        for i in range(10):
            thread = threading.Thread(
                target=lambda tid=i: results.append(create_nodes_operation(tid))
            )
            threads.append(thread)
        
        # Запускаем все потоки одновременно
        for thread in threads:
            thread.start()
        
        # Ждем завершения всех потоков
        for thread in threads:
            thread.join()
        
        # Проверяем результаты - все должны быть успешными
        self.assertEqual(len(results), 10)
        self.assertTrue(all(result == "success" for result in results))

    @patch('interface.pnet_session_manager.get_pnet_url')
    @patch('interface.pnet_session_manager.pf_login')
    @patch('interface.pnet_session_manager.create_all_lab_nodes_and_connectors')
    def test_exclusive_session_lock_exception_handling(self, mock_create_nodes, mock_pf_login, mock_get_pnet_url):
        """Тест эксклюзивной блокировки: блокировка освобождается даже при исключении"""
        # Мокаем внешние зависимости
        mock_get_pnet_url.return_value = "http://test-pnet.com"
        mock_pf_login.return_value = ("test_cookie", "test_xsrf")
        
        call_count = []
        call_lock = threading.Lock()
        
        # Мокаем функцию создания узлов: первая вызывает исключение, остальные успешны
        def mock_create_with_exception(*args, **kwargs):
            with call_lock:
                call_count.append(1)
                current_call = len(call_count)
            
            if current_call == 1:
                time.sleep(0.05)
                raise ValueError("Test exception")
            
            time.sleep(0.05)
            return "success"
        
        mock_create_nodes.side_effect = mock_create_with_exception
        
        # Выполняем логин
        self.session_manager.login()
        
        # Мокаем lab объект
        mock_lab = MagicMock()
        
        # Функция для выполнения в потоке
        def create_nodes_operation(thread_id):
            try:
                result = self.session_manager.create_lab_nodes_and_connectors(
                    mock_lab, f"lab_{thread_id}", f"user_{thread_id}"
                )
                return "success"
            except Exception as e:
                return f"error: {e}"
        
        # Создаем несколько потоков
        threads = []
        results = []
        
        for i in range(5):
            thread = threading.Thread(
                target=lambda tid=i: results.append(create_nodes_operation(tid))
            )
            threads.append(thread)
        
        # Запускаем все потоки одновременно
        for thread in threads:
            thread.start()
        
        # Ждем завершения всех потоков
        for thread in threads:
            thread.join()
        
        # Проверяем, что все потоки завершились (блокировка освободилась даже при исключении)
        self.assertEqual(len(results), 5)
        # Первый должен быть с ошибкой, остальные успешны
        error_results = [r for r in results if "error" in r]
        success_results = [r for r in results if r == "success"]
        self.assertEqual(len(error_results), 1)
        self.assertEqual(len(success_results), 4)


if __name__ == '__main__':
    unittest.main()
