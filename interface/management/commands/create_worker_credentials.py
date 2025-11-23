import random
import string
from django.core.management.base import BaseCommand
from interface.eveFunctions import pf_login, create_user
from interface.config import get_pnet_url, cache_for_minutes
from interface.utils import get_pnet_password
from dynamic_config.utils import get_worker_credentials, set_worker_credentials, get_config


class Command(BaseCommand):
    help = 'Создает PNet credentials для Gunicorn воркеров и сохраняет их в dynamic_config'

    def add_arguments(self, parser):
        parser.add_argument(
            '--workers',
            type=int,
            required=True,
            help='Количество воркеров для создания credentials'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать что будет сделано без выполнения изменений'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Пересоздать credentials даже если они уже существуют'
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

    @cache_for_minutes(5)
    def _get_admin_session(self, url):
        """Получить сессию администратора pnet_scripts с кэшированием"""
        cookie, xsrf = pf_login(url, 'pnet_scripts', 'eve')
        return cookie, xsrf

    def handle(self, *args, **options):
        workers_count = options['workers']
        dry_run = options['dry_run']
        force = options['force']
        password_length = options['password_length']

        self.stdout.write(
            self.style.SUCCESS(f"Начинаем создание credentials для {workers_count} воркеров")
        )

        if dry_run:
            self.stdout.write(self.style.WARNING("РЕЖИМ DRY RUN - изменения не будут применены!"))
        if force:
            self.stdout.write(self.style.WARNING("РЕЖИМ FORCE - credentials будут пересозданы!"))

        # Получаем URL PNet
        url = get_pnet_url()
        if not url:
            self.stdout.write(self.style.ERROR("PNET_URL не настроен в конфигурации"))
            return

        # Получаем административную сессию
        try:
            cookie, xsrf = self._get_admin_session(url)
            self.stdout.write(self.style.SUCCESS("Успешно авторизован как pnet_scripts"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Ошибка авторизации: {e}"))
            return

        # Счетчики
        success_count = 0
        error_count = 0
        skipped_count = 0

        # Обрабатываем каждого воркера
        for worker_id in range(1, workers_count + 1):
            # Проверяем, существуют ли уже credentials
            existing_creds = get_worker_credentials(worker_id)
            
            if not force and existing_creds:
                self.stdout.write(
                    self.style.WARNING(
                        f"Воркер {worker_id}: credentials уже существуют (username: {existing_creds.get('username')}) - пропускаем"
                    )
                )
                skipped_count += 1
                continue

            # Генерируем username и password
            username = f'worker_{worker_id}'
            random_password = self.generate_random_password(password_length)
            password = get_pnet_password(random_password)

            if dry_run:
                self.stdout.write(
                    f"DRY RUN: Создал бы пользователя {username} с паролем {password} "
                    f"и сохранил бы в WORKER_{worker_id}_CREDS"
                )
                success_count += 1
                continue

            # Создаем пользователя в PNet
            try:
                self.stdout.write(f"Создание пользователя {username} в PNet...")
                create_user(url, username, password, user_role='0', cookie=cookie)
                self.stdout.write(self.style.SUCCESS(f"✓ Пользователь {username} создан в PNet"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"✗ Ошибка создания пользователя {username}: {e}"))
                error_count += 1
                continue

            # Сохраняем credentials в dynamic_config
            try:
                set_worker_credentials(worker_id, username, password)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Credentials для воркера {worker_id} сохранены в dynamic_config (WORKER_{worker_id}_CREDS)"
                    )
                )
                success_count += 1
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"✗ Ошибка сохранения credentials для воркера {worker_id}: {e}")
                )
                error_count += 1

        # Статистика
        self.stdout.write("=" * 50)
        self.stdout.write("СТАТИСТИКА:")
        self.stdout.write(f"Всего воркеров: {workers_count}")
        self.stdout.write(f"Успешно создано: {success_count}")
        self.stdout.write(f"Пропущено: {skipped_count}")
        self.stdout.write(f"Ошибок: {error_count}")
        self.stdout.write("=" * 50)

