from django.core.management.base import BaseCommand
from django.core.exceptions import ValidationError
from interface.models import User, Platoon, LearningYear
from interface.forms import CustomUserCreationForm
import os


class Command(BaseCommand):
    help = 'Создает пользователей из файла со списком имен для указанного взвода'

    def add_arguments(self, parser):
        parser.add_argument(
            '-f',
            '--file',
            type=str,
            required=True,
            help='Путь к файлу со списком пользователей (формат: "Фамилия Имя" на каждой строке)'
        )
        parser.add_argument(
            '--platoon',
            type=int,
            required=True,
            help='Номер взвода'
        )

    def handle(self, *args, **options):
        file_path = options['file']
        platoon_number = options['platoon']

        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f'Файл {file_path} не найден'))
            return

        # Получаем или создаем взвод
        try:
            platoon = Platoon.objects.get(number=platoon_number)
        except Platoon.DoesNotExist:
            self.stdout.write(self.style.WARNING(f'Взвод с номером {platoon_number} не найден. Создаю новый взвод...'))
            platoon = Platoon.objects.create(number=platoon_number, learning_year=LearningYear.FIRST)
            self.stdout.write(self.style.SUCCESS(f'Взвод {platoon_number} создан'))

        self.stdout.write(f'Создание пользователей для взвода {platoon_number} из файла {file_path}')

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ошибка при чтении файла: {e}'))
            return

        created_count = 0
        skipped_count = 0
        error_count = 0

        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            
            if not line:
                continue

            parts = line.split()
            if len(parts) < 2:
                self.stdout.write(self.style.WARNING(f'Строка {line_num}: "{line}" - пропущена (неверный формат, ожидается "Фамилия Имя")'))
                error_count += 1
                continue

            first_name = parts[1]
            last_name = parts[0]
            username = f"{last_name}_{first_name}"

            # Проверяем, существует ли пользователь
            if User.objects.filter(username=username, platoon=platoon_number).exists():
                self.stdout.write(f'Пользователь {username} уже существует - пропускаем')
                skipped_count += 1
                continue

            # Создаем пользователя через CustomUserCreationForm
            try:
                form_data = {
                    'username': username,
                    'first_name': first_name,
                    'last_name': last_name,
                    'platoon': platoon.id,
                    'password1': 'test.test', 
                    'password2': 'test.test',
                }
                
                form = CustomUserCreationForm(data=form_data)
                
                if form.is_valid():
                    try:
                        user = form.save()
                        self.stdout.write(self.style.SUCCESS(f'[OK] Создан пользователь {username}'))
                        created_count += 1
                    except Exception as save_error:
                        # Обрабатываем ошибки при создании в Pnet/ELK
                        error_msg = str(save_error)
                        if 'ConnectTimeout' in error_msg or 'Connection' in error_msg:
                            self.stdout.write(self.style.WARNING(
                                f'[WARN] Пользователь {username} создан в БД, но не удалось создать в Pnet/ELK (нет подключения): {error_msg[:100]}'
                            ))
                            created_count += 1  
                        else:
                            self.stdout.write(self.style.ERROR(f'[ERROR] Ошибка при создании пользователя {username}: {error_msg[:200]}'))
                            error_count += 1
                else:
                    errors = '; '.join([f'{field}: {", ".join(errors)}' for field, errors in form.errors.items()])
                    self.stdout.write(self.style.ERROR(f'[ERROR] Ошибка валидации для {username}: {errors}'))
                    error_count += 1
            except Exception as e:
                error_msg = str(e)
                self.stdout.write(self.style.ERROR(f'[ERROR] Ошибка при создании пользователя {username}: {error_msg[:200]}'))
                error_count += 1

        # Статистика
        self.stdout.write("=" * 50)
        self.stdout.write("СТАТИСТИКА:")
        self.stdout.write(f"Успешно создано: {created_count}")
        self.stdout.write(f"Пропущено (уже существуют): {skipped_count}")
        self.stdout.write(f"Ошибок: {error_count}")
        self.stdout.write(f"Всего обработано строк: {len([l for l in lines if l.strip()])}")
        self.stdout.write("=" * 50)
