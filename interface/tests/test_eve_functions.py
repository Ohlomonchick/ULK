from unittest.mock import Mock, patch
from django.test import TestCase
import requests

from interface.eveFunctions import (
    retry_pnet_request, create_node, create_p2p, create_network, create_p2p_nat, destroy_session,
    UnauthorizedException
)


class RetryPnetRequestDecoratorTest(TestCase):
    """Тесты для декоратора retry_pnet_request"""

    def setUp(self):
        """Настройка перед каждым тестом"""
        # Создаем мок-функцию для тестирования декоратора
        self.mock_func = Mock()
        
    def test_successful_response_no_retry(self):
        """Тест: успешный ответ (200-399) не должен вызывать ретраи"""
        # Создаем успешный response
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 200
        self.mock_func.return_value = mock_response
        
        # Применяем декоратор
        decorated_func = retry_pnet_request(max_attempts=3)(self.mock_func)
        
        # Вызываем функцию
        result = decorated_func('url', {}, {}, 'xsrf')
        
        # Проверяем, что функция вызвана только один раз
        self.assertEqual(self.mock_func.call_count, 1)
        # Проверяем, что возвращен правильный результат
        self.assertEqual(result, mock_response)
        
    def test_successful_response_300_range_no_retry(self):
        """Тест: успешный ответ в диапазоне 300-399 не должен вызывать ретраи"""
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 301
        self.mock_func.return_value = mock_response
        
        decorated_func = retry_pnet_request(max_attempts=3)(self.mock_func)
        result = decorated_func('url', {}, {}, 'xsrf')
        
        self.assertEqual(self.mock_func.call_count, 1)
        self.assertEqual(result, mock_response)
        
    def test_timeout_retries_and_logs(self):
        """Тест: Timeout должен вызывать ретраи и логировать на последней попытке"""
        # Настраиваем функцию, чтобы она всегда выбрасывала Timeout
        self.mock_func.side_effect = requests.exceptions.Timeout("Connection timeout")
        
        decorated_func = retry_pnet_request(max_attempts=3)(self.mock_func)
        
        # Проверяем логирование
        with patch('interface.eveFunctions.logger') as mock_logger:
            with self.assertRaises(requests.exceptions.Timeout):
                decorated_func('url', {}, {}, 'xsrf')
            
            # Проверяем, что функция вызвана 3 раза (max_attempts)
            self.assertEqual(self.mock_func.call_count, 3)
            
            # Проверяем, что на последней попытке было логирование ошибки
            error_calls = [call for call in mock_logger.error.call_args_list 
                          if 'Timeout after 3 attempts' in str(call)]
            self.assertGreater(len(error_calls), 0, "Должно быть логирование Timeout на последней попытке")
            
    def test_bad_http_response_retries_and_logs(self):
        """Тест: плохой HTTP ответ (400+) должен вызывать ретраи и логировать на последней попытке"""
        # Создаем плохой response
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 500
        
        self.mock_func.return_value = mock_response
        
        decorated_func = retry_pnet_request(max_attempts=3)(self.mock_func)
        
        # Проверяем логирование
        with patch('interface.eveFunctions.logger') as mock_logger:
            result = decorated_func('url', {}, {}, 'xsrf')
            
            # Проверяем, что функция вызвана 3 раза
            self.assertEqual(self.mock_func.call_count, 3)
            
            # Проверяем, что на последней попытке было логирование ошибки
            error_calls = [call for call in mock_logger.error.call_args_list 
                          if 'HTTP 500 response after 3 attempts' in str(call)]
            self.assertGreater(len(error_calls), 0, "Должно быть логирование HTTP ошибки на последней попытке")
            
            # Проверяем, что возвращен response (не исключение)
            self.assertEqual(result, mock_response)
            
    def test_bad_http_response_400_retries(self):
        """Тест: HTTP 400 должен вызывать ретраи"""
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 400
        
        self.mock_func.return_value = mock_response
        
        decorated_func = retry_pnet_request(max_attempts=3)(self.mock_func)
        
        with patch('interface.eveFunctions.logger') as mock_logger:
            result = decorated_func('url', {}, {}, 'xsrf')
            
            # Проверяем, что функция вызвана 3 раза
            self.assertEqual(self.mock_func.call_count, 3)
            
            # Проверяем логирование
            error_calls = [call for call in mock_logger.error.call_args_list 
                          if 'HTTP 400 response after 3 attempts' in str(call)]
            self.assertGreater(len(error_calls), 0)
            
    def test_request_exception_retries_and_logs(self):
        """Тест: RequestException должен вызывать ретраи и логировать на последней попытке"""
        # Настраиваем функцию, чтобы она выбрасывала ConnectionError
        self.mock_func.side_effect = requests.exceptions.ConnectionError("Connection failed")
        
        decorated_func = retry_pnet_request(max_attempts=3)(self.mock_func)
        
        with patch('interface.eveFunctions.logger') as mock_logger:
            with self.assertRaises(requests.exceptions.ConnectionError):
                decorated_func('url', {}, {}, 'xsrf')
            
            # Проверяем, что функция вызвана 3 раза
            self.assertEqual(self.mock_func.call_count, 3)
            
            # Проверяем логирование
            error_calls = [call for call in mock_logger.error.call_args_list 
                          if 'Request exception after 3 attempts' in str(call)]
            self.assertGreater(len(error_calls), 0)
            
    def test_generic_exception_retries_and_logs(self):
        """Тест: общее исключение должно вызывать ретраи и логировать на последней попытке"""
        self.mock_func.side_effect = ValueError("Some error")
        
        decorated_func = retry_pnet_request(max_attempts=3)(self.mock_func)
        
        with patch('interface.eveFunctions.logger') as mock_logger:
            with self.assertRaises(ValueError):
                decorated_func('url', {}, {}, 'xsrf')
            
            # Проверяем, что функция вызвана 3 раза
            self.assertEqual(self.mock_func.call_count, 3)
            
            # Проверяем логирование
            error_calls = [call for call in mock_logger.error.call_args_list 
                          if 'Exception after 3 attempts' in str(call)]
            self.assertGreater(len(error_calls), 0)
            
    def test_success_after_retry(self):
        """Тест: успешный ответ после неудачных попыток"""
        # Первые две попытки - плохой ответ, третья - успешный
        bad_response = Mock(spec=requests.Response)
        bad_response.status_code = 500
        
        good_response = Mock(spec=requests.Response)
        good_response.status_code = 200
        
        self.mock_func.side_effect = [
            bad_response,  # Первая попытка
            bad_response,  # Вторая попытка
            good_response  # Третья попытка - успех
        ]
        
        decorated_func = retry_pnet_request(max_attempts=3)(self.mock_func)
        
        result = decorated_func('url', {}, {}, 'xsrf')
        
        # Проверяем, что функция вызвана 3 раза
        self.assertEqual(self.mock_func.call_count, 3)
        # Проверяем, что возвращен успешный response
        self.assertEqual(result, good_response)
        self.assertEqual(result.status_code, 200)
        
    def test_success_after_timeout(self):
        """Тест: успешный ответ после таймаутов"""
        good_response = Mock(spec=requests.Response)
        good_response.status_code = 200
        
        self.mock_func.side_effect = [
            requests.exceptions.Timeout("Timeout 1"),
            requests.exceptions.Timeout("Timeout 2"),
            good_response  # Третья попытка - успех
        ]
        
        decorated_func = retry_pnet_request(max_attempts=3)(self.mock_func)
        
        result = decorated_func('url', {}, {}, 'xsrf')
        
        # Проверяем, что функция вызвана 3 раза
        self.assertEqual(self.mock_func.call_count, 3)
        # Проверяем, что возвращен успешный response
        self.assertEqual(result, good_response)
        
    def test_custom_max_attempts(self):
        """Тест: кастомное количество попыток"""
        self.mock_func.side_effect = requests.exceptions.Timeout("Timeout")
        
        decorated_func = retry_pnet_request(max_attempts=5)(self.mock_func)
        
        with patch('interface.eveFunctions.logger') as mock_logger:
            with self.assertRaises(requests.exceptions.Timeout):
                decorated_func('url', {}, {}, 'xsrf')
            
            # Проверяем, что функция вызвана 5 раз
            self.assertEqual(self.mock_func.call_count, 5)
            
            # Проверяем логирование с правильным количеством попыток
            error_calls = [call for call in mock_logger.error.call_args_list 
                          if 'Timeout after 5 attempts' in str(call)]
            self.assertGreater(len(error_calls), 0)
            
    def test_function_name_in_log(self):
        """Тест: название функции должно быть в логе"""
        # Создаем мок с атрибутом __name__
        mock_func_with_name = Mock()
        mock_func_with_name.side_effect = requests.exceptions.Timeout("Timeout")
        mock_func_with_name.configure_mock(__name__='test_function_name')
        
        decorated_func = retry_pnet_request(max_attempts=3)(mock_func_with_name)
        
        with patch('interface.eveFunctions.logger') as mock_logger:
            with self.assertRaises(requests.exceptions.Timeout):
                decorated_func('url', {}, {}, 'xsrf')
            
            # Проверяем, что в логе есть название функции
            error_calls = mock_logger.error.call_args_list
            found_function_name = False
            for call in error_calls:
                if 'test_function_name' in str(call):
                    found_function_name = True
                    break
            self.assertTrue(found_function_name, "Название функции должно быть в логе ошибки")
            
    def test_non_response_return_value(self):
        """Тест: функция, возвращающая не-response объект, не должна проверять статус код"""
        self.mock_func.return_value = "some_string"
        
        decorated_func = retry_pnet_request(max_attempts=3)(self.mock_func)
        
        result = decorated_func('url', {}, {}, 'xsrf')
        
        # Проверяем, что функция вызвана один раз
        self.assertEqual(self.mock_func.call_count, 1)
        # Проверяем, что возвращено значение без проверки
        self.assertEqual(result, "some_string")
        
    def test_real_function_name_in_log(self):
        """Тест: реальная функция должна получать правильное имя в логе"""
        def real_test_function():
            """Тестовая функция для проверки имени"""
            raise requests.exceptions.Timeout("Test timeout")
        
        decorated_func = retry_pnet_request(max_attempts=3)(real_test_function)
        
        with patch('interface.eveFunctions.logger') as mock_logger:
            with self.assertRaises(requests.exceptions.Timeout):
                decorated_func()
            
            # Проверяем, что в логе есть правильное имя функции
            error_calls = mock_logger.error.call_args_list
            found_function_name = False
            for call in error_calls:
                if 'real_test_function' in str(call):
                    found_function_name = True
                    break
            self.assertTrue(found_function_name, "Название реальной функции должно быть в логе ошибки")
    
    def test_412_unauthorized_no_retry(self):
        """Тест: 412 Unauthorized не должен вызывать ретраи, а выбрасывать UnauthorizedException"""
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 412
        mock_response.text = '{"code":412,"status":"unauthorized","message":"User is not authenticated"}'
        self.mock_func.return_value = mock_response
        
        decorated_func = retry_pnet_request(max_attempts=3)(self.mock_func)
        
        with patch('interface.eveFunctions.logger') as mock_logger:
            with self.assertRaises(UnauthorizedException) as context:
                decorated_func('url', {}, {}, 'xsrf')
            
            # Проверяем, что функция вызвана только один раз (без ретраев)
            self.assertEqual(self.mock_func.call_count, 1)
            
            # Проверяем, что исключение содержит response
            self.assertEqual(context.exception.response, mock_response)
            
            # Проверяем логирование предупреждения
            warning_calls = [call for call in mock_logger.warning.call_args_list 
                           if 'Unauthorized (412)' in str(call)]
            self.assertGreater(len(warning_calls), 0, "Должно быть логирование предупреждения о 412")
    
    def test_412_unauthorized_vs_other_errors(self):
        """Тест: 412 выбрасывает UnauthorizedException, другие ошибки ретраятся"""
        # Первый вызов - 412, второй - 500
        unauthorized_response = Mock(spec=requests.Response)
        unauthorized_response.status_code = 412
        unauthorized_response.text = '{"code":412,"status":"unauthorized"}'
        
        bad_response = Mock(spec=requests.Response)
        bad_response.status_code = 500
        
        self.mock_func.side_effect = [unauthorized_response, bad_response]
        
        decorated_func = retry_pnet_request(max_attempts=3)(self.mock_func)
        
        # 412 должен выбрасывать UnauthorizedException сразу, без ретраев
        with self.assertRaises(UnauthorizedException):
            decorated_func('url', {}, {}, 'xsrf')
        
        # Проверяем, что функция вызвана только один раз
        self.assertEqual(self.mock_func.call_count, 1)


class RealFunctionsRetryTest(TestCase):
    """Тесты ретраев для реальных функций eveFunctions с мокированием requests"""

    def setUp(self):
        """Настройка перед каждым тестом"""
        self.test_url = "http://test-pnet.com"
        self.test_cookie = {"session": "test_session"}
        self.test_xsrf = "test_xsrf_token"
        
    @patch('interface.eveFunctions.requests.post')
    def test_create_node_timeout_retries(self, mock_post):
        """Тест: create_node делает ретраи при Timeout"""
        # Настраиваем мок, чтобы он выбрасывал Timeout
        mock_post.side_effect = requests.exceptions.Timeout("Connection timeout")
        
        with patch('interface.eveFunctions.logger') as mock_logger:
            with self.assertRaises(requests.exceptions.Timeout):
                create_node(self.test_url, {"template": "test"}, self.test_cookie, self.test_xsrf)
            
            # Проверяем, что requests.post вызван 3 раза
            self.assertEqual(mock_post.call_count, 3)
            
            # Проверяем логирование
            error_calls = [call for call in mock_logger.error.call_args_list 
                          if 'Error in create_node' in str(call) and 'Timeout' in str(call)]
            self.assertGreater(len(error_calls), 0, "Должно быть логирование Timeout для create_node")
            
    @patch('interface.eveFunctions.requests.post')
    def test_create_node_bad_response_retries(self, mock_post):
        """Тест: create_node делает ретраи при плохом HTTP ответе"""
        # Создаем плохой response
        bad_response = Mock(spec=requests.Response)
        bad_response.status_code = 500
        bad_response.json.return_value = {"message": "Internal Server Error"}
        
        mock_post.return_value = bad_response
        
        with patch('interface.eveFunctions.logger') as mock_logger:
            result = create_node(self.test_url, {"template": "test"}, self.test_cookie, self.test_xsrf)
            
            # Проверяем, что requests.post вызван 3 раза
            self.assertEqual(mock_post.call_count, 3)
            
            # Проверяем логирование
            error_calls = [call for call in mock_logger.error.call_args_list 
                          if 'Error in create_node' in str(call) and 'HTTP 500' in str(call)]
            self.assertGreater(len(error_calls), 0, "Должно быть логирование HTTP ошибки для create_node")
            
            # Проверяем, что возвращен response
            self.assertEqual(result, bad_response)
            
    @patch('interface.eveFunctions.requests.post')
    def test_create_p2p_timeout_retries(self, mock_post):
        """Тест: create_p2p делает ретраи при Timeout"""
        mock_post.side_effect = requests.exceptions.Timeout("Connection timeout")
        
        with patch('interface.eveFunctions.logger') as mock_logger:
            with self.assertRaises(requests.exceptions.Timeout):
                create_p2p(self.test_url, {"name": "test_p2p"}, self.test_cookie)
            
            self.assertEqual(mock_post.call_count, 3)
            
            error_calls = [call for call in mock_logger.error.call_args_list 
                          if 'Error in create_p2p' in str(call) and 'Timeout' in str(call)]
            self.assertGreater(len(error_calls), 0)
            
    @patch('interface.eveFunctions.requests.post')
    def test_create_network_success_after_retry(self, mock_post):
        """Тест: create_network успешно выполняется после ретраев"""
        # Первые две попытки - плохой ответ, третья - успешный
        bad_response = Mock(spec=requests.Response)
        bad_response.status_code = 500
        bad_response.json.return_value = {"message": "Error"}
        
        good_response = Mock(spec=requests.Response)
        good_response.status_code = 200
        good_response.json.return_value = {"message": "Network created"}
        
        mock_post.side_effect = [bad_response, bad_response, good_response]
        
        result = create_network(self.test_url, {"name": "test_network"}, self.test_cookie)
        
        # Проверяем, что requests.post вызван 3 раза
        self.assertEqual(mock_post.call_count, 3)
        # Проверяем, что возвращен успешный response
        self.assertEqual(result, good_response)
        self.assertEqual(result.status_code, 200)
        
    @patch('interface.eveFunctions.requests.post')
    def test_create_p2p_nat_bad_response_retries(self, mock_post):
        """Тест: create_p2p_nat делает ретраи при плохом HTTP ответе"""
        bad_response = Mock(spec=requests.Response)
        bad_response.status_code = 400
        bad_response.json.return_value = {"message": "Bad Request"}
        
        mock_post.return_value = bad_response
        
        with patch('interface.eveFunctions.logger') as mock_logger:
            result = create_p2p_nat(self.test_url, {"node_id": "test_node"}, self.test_cookie)
            
            self.assertEqual(mock_post.call_count, 3)
            
            error_calls = [call for call in mock_logger.error.call_args_list 
                          if 'Error in create_p2p_nat' in str(call) and 'HTTP 400' in str(call)]
            self.assertGreater(len(error_calls), 0)
            
    @patch('interface.eveFunctions.requests.post')
    def test_destroy_session_timeout_retries(self, mock_post):
        """Тест: destroy_session делает ретраи при Timeout"""
        mock_post.side_effect = requests.exceptions.Timeout("Connection timeout")
        
        with patch('interface.eveFunctions.logger') as mock_logger:
            with self.assertRaises(requests.exceptions.Timeout):
                destroy_session(self.test_url, 12345, self.test_cookie)
            
            self.assertEqual(mock_post.call_count, 3)
            
            error_calls = [call for call in mock_logger.error.call_args_list 
                          if 'Error in destroy_session' in str(call) and 'Timeout' in str(call)]
            self.assertGreater(len(error_calls), 0)
            
    @patch('interface.eveFunctions.requests.post')
    def test_create_node_success_no_retry(self, mock_post):
        """Тест: create_node не делает ретраи при успешном ответе"""
        good_response = Mock(spec=requests.Response)
        good_response.status_code = 200
        good_response.json.return_value = {"message": "Node created"}
        
        mock_post.return_value = good_response
        
        result = create_node(self.test_url, {"template": "test"}, self.test_cookie, self.test_xsrf)
        
        # Проверяем, что requests.post вызван только один раз
        self.assertEqual(mock_post.call_count, 1)
        # Проверяем, что возвращен успешный response
        self.assertEqual(result, good_response)
    
    @patch('interface.eveFunctions.requests.post')
    def test_create_node_412_unauthorized_no_retry(self, mock_post):
        """Тест: create_node выбрасывает UnauthorizedException при 412 без ретраев"""
        unauthorized_response = Mock(spec=requests.Response)
        unauthorized_response.status_code = 412
        unauthorized_response.text = '{"code":412,"status":"unauthorized","message":"User is not authenticated"}'
        
        mock_post.return_value = unauthorized_response
        
        with patch('interface.eveFunctions.logger') as mock_logger:
            with self.assertRaises(UnauthorizedException) as context:
                create_node(self.test_url, {"template": "test"}, self.test_cookie, self.test_xsrf)
            
            # Проверяем, что requests.post вызван только один раз (без ретраев)
            self.assertEqual(mock_post.call_count, 1)
            
            # Проверяем, что исключение содержит response
            self.assertEqual(context.exception.response, unauthorized_response)
            
            # Проверяем логирование предупреждения
            warning_calls = [call for call in mock_logger.warning.call_args_list 
                           if 'Unauthorized (412)' in str(call)]
            self.assertGreater(len(warning_calls), 0, "Должно быть логирование предупреждения о 412")

