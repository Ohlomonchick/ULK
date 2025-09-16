from django.core.management.base import BaseCommand
import random
import string
from interface.models import User
from interface.elastic_utils import create_elastic_user, get_elastic_client
from interface.utils import get_pnet_password


class Command(BaseCommand):
    help = 'Создает пользователей Elasticsearch для всех пользователей приложения'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать что будет сделано без выполнения изменений'
        )
        parser.add_argument(
            '--index',
            type=str,
            default='suricata-*',
            help='Индекс Elasticsearch для доступа (по умолчанию suricata-*)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Пересоздать пользователей даже если они уже существуют'
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

    def check_user_exists(self, username):
        """Проверяет существование пользователя в Elasticsearch"""
        try:
            client = get_elastic_client()
            if not client:
                return False
            response = client.security.get_user(username=username)
            return username in response
        except:
            return False

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        index = options['index']
        force = options['force']
        password_length = options['password_length']

        self.stdout.write(
            self.style.SUCCESS("Начинаем создание пользователей Elasticsearch")
        )

        if dry_run:
            self.stdout.write(self.style.WARNING("РЕЖИМ DRY RUN - изменения не будут применены!"))
        if force:
            self.stdout.write(self.style.WARNING("РЕЖИМ FORCE - пользователи будут пересозданы!"))

        # Получаем всех пользователей
        users = User.objects.all()
        self.stdout.write(f"Найдено {users.count()} пользователей в базе данных")

        if not users.exists():
            self.stdout.write(self.style.WARNING("Пользователи не найдены в базе данных"))
            return

        # Счетчики
        success_count = 0
        error_count = 0
        skipped_count = 0

        # Обрабатываем каждого пользователя
        for user in users:
            # Пропускаем пользователей без pnet_login
            if not user.pnet_login:
                self.stdout.write(f"Пользователь {user.username} не имеет pnet_login - пропускаем")
                skipped_count += 1
                continue

            # Определяем пароль для использования
            if user.pnet_password:
                password = user.pnet_password
            else:
                # Генерируем случайный пароль и сохраняем его
                random_password = self.generate_random_password(password_length)
                password = get_pnet_password(random_password)
                user.pnet_password = password
                user.save()
                self.stdout.write(f"Сгенерирован новый пароль для пользователя {user.username}")

            # Проверяем существование пользователя
            if not force and self.check_user_exists(user.pnet_login):
                self.stdout.write(f"Пользователь {user.pnet_login} уже существует - пропускаем")
                skipped_count += 1
                continue

            if dry_run:
                self.stdout.write(f"DRY RUN: Создал бы пользователя {user.pnet_login} с паролем {password}")
                success_count += 1
                continue

            # Создаем пользователя
            self.stdout.write(f"Создание пользователя {user.pnet_login}...")
            result = create_elastic_user(user.pnet_login, password, index)

            if result == 'created':
                self.stdout.write(self.style.SUCCESS(f"✓ Пользователь {user.pnet_login} создан"))
                success_count += 1
            else:
                self.stdout.write(self.style.ERROR(f"✗ Ошибка создания {user.pnet_login}: {result}"))
                error_count += 1

        # Статистика
        self.stdout.write("=" * 50)
        self.stdout.write("СТАТИСТИКА:")
        self.stdout.write(f"Всего пользователей: {users.count()}")
        self.stdout.write(f"Успешно создано: {success_count}")
        self.stdout.write(f"Пропущено: {skipped_count}")
        self.stdout.write(f"Ошибок: {error_count}")
        self.stdout.write(f"Индекс: {index}")
        self.stdout.write("=" * 50)
