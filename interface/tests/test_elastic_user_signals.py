from django.test import TestCase
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock
from interface.models import User, Platoon
from interface.elastic_utils import delete_elastic_user

User = get_user_model()


class ElasticUserSignalsTest(TestCase):
    """Тесты для сигналов автоматического удаления пользователей из Elasticsearch"""

    def setUp(self):
        """Настройка тестовых данных"""
        # Создаем тестовый взвод
        self.platoon = Platoon.objects.create(number=1)

        # Создаем тестового пользователя
        self.user = User.objects.create_user(
            username='test_user',
            first_name='Test',
            last_name='User',
            email='test@example.com',
            platoon=self.platoon
        )

    @patch('interface.models.delete_elastic_user')
    def test_user_deletion_triggers_elasticsearch_cleanup(self, mock_delete_elastic):
        """Тест: удаление пользователя должно вызывать удаление из Elasticsearch"""
        # Настраиваем мок
        mock_delete_elastic.return_value = 'deleted'

        # Проверяем, что у пользователя есть pnet_login
        self.assertIsNotNone(self.user.pnet_login)

        # Удаляем пользователя
        user_pnet_login = self.user.pnet_login
        self.user.delete()

        # Проверяем, что функция delete_elastic_user была вызвана с правильным логином
        mock_delete_elastic.assert_called_once_with(user_pnet_login)

    @patch('interface.models.delete_elastic_user')
    def test_user_deletion_handles_elasticsearch_errors(self, mock_delete_elastic):
        """Тест: обработка ошибок при удалении из Elasticsearch"""
        # Настраиваем мок для возврата ошибки
        mock_delete_elastic.return_value = 'connection failed'

        # Удаление пользователя не должно вызывать исключение
        # даже если Elasticsearch недоступен
        try:
            self.user.delete()
        except Exception as e:
            self.fail(f"User deletion should not raise exception: {e}")

        # Проверяем, что функция была вызвана
        mock_delete_elastic.assert_called_once()

    @patch('interface.models.delete_elastic_user')
    def test_user_deletion_with_empty_pnet_login_after_slugify(self, mock_delete_elastic):
        """Тест: пользователь с пустым pnet_login после slugify не должен вызывать удаление из Elasticsearch"""
        # Создаем пользователя с именем, которое при slugify даст пустую строку
        # Используем только специальные символы, которые slugify удалит
        user_with_empty_pnet = User.objects.create_user(
            username='---',
            first_name='---',
            last_name='---',
            email='empty@example.com',
            platoon=self.platoon
        )

        # Проверяем, что pnet_login действительно пустой после slugify
        self.assertEqual(user_with_empty_pnet.pnet_login, '')

        # Удаляем пользователя
        user_with_empty_pnet.delete()

        # Проверяем, что функция delete_elastic_user не была вызвана
        mock_delete_elastic.assert_not_called()

