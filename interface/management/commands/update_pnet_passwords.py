from django.core.management.base import BaseCommand
import os
import random
import string
import logging
from interface.models import User
from interface.utils import get_pnet_password
from interface.pnet_session_manager import PNetSessionManager
from interface.config import get_pnet_url, get_pnet_base_dir


class Command(BaseCommand):
    help = 'Обновляет пароли всех пользователей в PNETLab'

    def add_arguments(self, parser):
        parser.add_argument(
            '--url',
            type=str,
            help='URL PNETLab (если не указан, используется из настроек или переменной окружения PNET_URL)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать что будет сделано без выполнения изменений'
        )
        parser.add_argument(
            '--password-length',
            type=int,
            default=12,
            help='Длина генерируемого пароля (по умолчанию 12)'
        )

    def generate_random_password(self, length=12):
        """Генерирует случайный пароль заданной длины"""
        characters = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(random.choice(characters) for _ in range(length))

    def update_user_pnet_password(self, user, session, password_length, dry_run=False):
        """Обновляет пароль пользователя в PNETLab. session — PNetSessionManager или None при dry_run."""
        try:
            # Генерируем случайный пароль
            random_password = self.generate_random_password(password_length)

            pnet_password = get_pnet_password(random_password)

            self.stdout.write(
                self.style.SUCCESS(
                    f"Обновление пароля для пользователя {user.username} (pnet_login: {user.pnet_login})"
                )
            )

            if dry_run:
                self.stdout.write(
                    self.style.WARNING(f"DRY RUN: Пароль будет: {random_password} -> PNET: {pnet_password}")
                )
                return True

            # Пытаемся изменить пароль пользователя через сессию
            result = session.change_user_password(user.pnet_login, pnet_password)
            if result is not None:
                self.stdout.write(
                    self.style.SUCCESS(f"Пароль пользователя {user.pnet_login} успешно обновлен в PNETLab")
                )
            else:
                # Пользователь не существует в PNETLab, создаем его
                self.stdout.write(
                    self.style.WARNING(f"Пользователь {user.pnet_login} не найден в PNETLab, создаем...")
                )

                # Создаем директорию для пользователя
                session.create_directory(get_pnet_base_dir(), user.pnet_login)

                # Создаем пользователя
                session.create_user(user.pnet_login, pnet_password)

                self.stdout.write(
                    self.style.SUCCESS(f"Пользователь {user.pnet_login} успешно создан в PNETLab")
                )

            # Обновляем пароль в базе данных Django
            user.pnet_password = pnet_password
            user.save()

            self.stdout.write(
                self.style.SUCCESS(f"Пароль пользователя {user.username} обновлен в базе данных Django")
            )

            return True

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Ошибка при обновлении пароля для пользователя {user.username}: {str(e)}")
            )
            return False

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS("Начинаем обновление паролей пользователей в PNETLab")
        )

        # Получаем URL PNETLab
        pnet_url = options['url'] or os.environ.get('PNET_URL', get_pnet_url())
        self.stdout.write(f"Используем PNETLab URL: {pnet_url}")

        # Проверяем режим dry-run
        dry_run = options['dry_run']
        if dry_run:
            self.stdout.write(
                self.style.WARNING("РЕЖИМ DRY RUN - изменения не будут применены!")
            )

        password_length = options['password_length']

        try:
            # Получаем всех пользователей из базы данных
            users = User.objects.all()
            self.stdout.write(f"Найдено {users.count()} пользователей в базе данных")

            if not users.exists():
                self.stdout.write(
                    self.style.WARNING("Пользователи не найдены в базе данных")
                )
                return

            if not dry_run:
                session = PNetSessionManager(do_logout=True)
                self.stdout.write("Авторизация в PNETLab...")
                session.login(url=pnet_url)
                self.stdout.write(
                    self.style.SUCCESS("Успешная авторизация в PNETLab")
                )
            else:
                session = None

            # Счетчики для статистики
            success_count = 0
            error_count = 0

            # Обрабатываем каждого пользователя
            for user in users:
                if self.update_user_pnet_password(user, session, password_length, dry_run):
                    success_count += 1
                else:
                    error_count += 1

            if not dry_run:
                session.logout()
                self.stdout.write("Выход из PNETLab")

            # Выводим статистику
            self.stdout.write("=" * 50)
            self.stdout.write("СТАТИСТИКА ОБНОВЛЕНИЯ ПАРОЛЕЙ:")
            self.stdout.write(f"Всего пользователей: {users.count()}")
            self.stdout.write(f"Успешно обновлено: {success_count}")
            self.stdout.write(f"Ошибок: {error_count}")
            self.stdout.write("=" * 50)

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Критическая ошибка: {str(e)}")
            )
            raise
