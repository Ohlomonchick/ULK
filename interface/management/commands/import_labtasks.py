import json
import os
from django.core.management.base import BaseCommand
from django.db import transaction
from interface.models import LabTask, Lab, LabLevel


class Command(BaseCommand):
    help = 'Импортирует LabTask и LabLevel из JSON файла и привязывает их к лабораторным работам по slug'

    def add_arguments(self, parser):
        parser.add_argument(
            '--input',
            type=str,
            required=True,
            help='Путь к входному JSON файлу с данными LabTask и LabLevel (поддерживает форматы экспорта и плоский массив)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать что будет сделано без выполнения изменений'
        )
        parser.add_argument(
            '--update-existing',
            action='store_true',
            help='Обновить существующие LabTask и LabLevel если они найдены по task_id/level_number и lab'
        )
        parser.add_argument(
            '--skip-missing-labs',
            action='store_true',
            help='Пропустить задания для лабораторных работ, которые не найдены в базе'
        )

    def validate_task_data(self, task_data):
        """Валидирует данные задания или уровня"""
        # Определяем тип записи
        record_type = task_data.get('type', 'task')  # по умолчанию task
        
        if record_type == 'level':
            # Валидация для LabLevel
            required_fields = ['level_number', 'description', 'lab_slug']
            missing_fields = [field for field in required_fields if not task_data.get(field)]
            
            if missing_fields:
                return False, f"Отсутствуют обязательные поля для уровня: {', '.join(missing_fields)}"
            
            # Проверяем что level_number является числом
            try:
                int(task_data['level_number'])
            except (ValueError, TypeError):
                return False, "level_number должен быть числом"
                
        else:
            # Валидация для LabTask
            required_fields = ['task_id', 'description', 'lab_slug']
            missing_fields = [field for field in required_fields if not task_data.get(field)]
            
            if missing_fields:
                return False, f"Отсутствуют обязательные поля для задания: {', '.join(missing_fields)}"
        
        return True, None

    def handle(self, *args, **options):
        input_file = options['input']
        dry_run = options['dry_run']
        update_existing = options['update_existing']
        skip_missing_labs = options['skip_missing_labs']
        
        # Проверяем существование файла
        if not os.path.exists(input_file):
            self.stdout.write(
                self.style.ERROR(f'Файл {input_file} не найден')
            )
            return
        
        try:
            # Читаем JSON файл
            with open(input_file, 'r', encoding='utf-8') as f:
                import_data = json.load(f)
            
            # Поддерживаем два формата:
            # 1. Плоский массив с полем type
            # 2. Объект с отдельными массивами lab_tasks и lab_levels
            if isinstance(import_data, dict):
                # Формат экспорта с отдельными массивами
                tasks_data = import_data.get('lab_tasks', [])
                levels_data = import_data.get('lab_levels', [])
                
                # Преобразуем в плоский формат
                import_data = []
                for task in tasks_data:
                    task['type'] = 'task'
                    import_data.append(task)
                for level in levels_data:
                    level['type'] = 'level'
                    import_data.append(level)
                    
            elif not isinstance(import_data, list):
                self.stdout.write(
                    self.style.ERROR('JSON файл должен содержать массив объектов или объект с полями lab_tasks и lab_levels')
                )
                return
            
            self.stdout.write(f'Загружено {len(import_data)} записей из файла {input_file}')
            
            if dry_run:
                self.stdout.write(
                    self.style.WARNING('РЕЖИМ DRY RUN - изменения не будут применены!')
                )
            
            # Статистика
            stats = {
                'processed': 0,
                'tasks_created': 0,
                'tasks_updated': 0,
                'tasks_skipped': 0,
                'levels_created': 0,
                'levels_updated': 0,
                'levels_skipped': 0,
                'errors': 0,
                'missing_labs': 0
            }
            
            # Получаем все существующие Lab для быстрого поиска
            existing_labs = {lab.slug: lab for lab in Lab.objects.all()}
            
            with transaction.atomic():
                for i, task_data in enumerate(import_data, 1):
                    stats['processed'] += 1
                    
                    # Валидируем данные
                    is_valid, error_msg = self.validate_task_data(task_data)
                    if not is_valid:
                        self.stdout.write(
                            self.style.ERROR(f'Запись #{i}: {error_msg}')
                        )
                        stats['errors'] += 1
                        continue
                    
                    lab_slug = task_data['lab_slug']
                    description = task_data['description']
                    record_type = task_data.get('type', 'task')
                    
                    # Проверяем существование лабораторной работы
                    if lab_slug not in existing_labs:
                        if skip_missing_labs:
                            self.stdout.write(
                                self.style.WARNING(
                                    f'Запись #{i}: Лабораторная работа с slug "{lab_slug}" не найдена, пропускаем'
                                )
                            )
                            stats['missing_labs'] += 1
                            continue
                        else:
                            self.stdout.write(
                                self.style.ERROR(
                                    f'Запись #{i}: Лабораторная работа с slug "{lab_slug}" не найдена'
                                )
                            )
                            stats['errors'] += 1
                            continue
                    
                    lab = existing_labs[lab_slug]
                    
                    if record_type == 'level':
                        # Обработка LabLevel
                        level_number = int(task_data['level_number'])
                        
                        # Ищем существующий уровень
                        existing_level = LabLevel.objects.filter(
                            lab=lab,
                            level_number=level_number
                        ).first()
                        
                        if existing_level:
                            if update_existing:
                                if not dry_run:
                                    existing_level.description = description
                                    existing_level.save()
                                
                                self.stdout.write(
                                    self.style.SUCCESS(
                                        f'Запись #{i}: Обновлен уровень {level_number} для лаборатории {lab_slug}'
                                    )
                                )
                                stats['levels_updated'] += 1
                            else:
                                self.stdout.write(
                                    self.style.WARNING(
                                        f'Запись #{i}: Уровень {level_number} уже существует для лаборатории {lab_slug}, пропускаем'
                                    )
                                )
                                stats['levels_skipped'] += 1
                        else:
                            # Создаем новый уровень
                            if not dry_run:
                                LabLevel.objects.create(
                                    lab=lab,
                                    level_number=level_number,
                                    description=description
                                )
                            
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'Запись #{i}: Создан уровень {level_number} для лаборатории {lab_slug}'
                                )
                            )
                            stats['levels_created'] += 1
                    else:
                        # Обработка LabTask
                        task_id = task_data['task_id']
                        json_config = task_data.get('json_config', {})
                        
                        # Ищем существующее задание
                        existing_task = LabTask.objects.filter(
                            lab=lab,
                            task_id=task_id
                        ).first()
                        
                        if existing_task:
                            if update_existing:
                                if not dry_run:
                                    existing_task.description = description
                                    existing_task.json_config = json_config
                                    existing_task.save()
                                
                                self.stdout.write(
                                    self.style.SUCCESS(
                                        f'Запись #{i}: Обновлено задание {task_id} для лаборатории {lab_slug}'
                                    )
                                )
                                stats['tasks_updated'] += 1
                            else:
                                self.stdout.write(
                                    self.style.WARNING(
                                        f'Запись #{i}: Задание {task_id} уже существует для лаборатории {lab_slug}, пропускаем'
                                    )
                                )
                                stats['tasks_skipped'] += 1
                        else:
                            # Создаем новое задание
                            if not dry_run:
                                LabTask.objects.create(
                                    lab=lab,
                                    task_id=task_id,
                                    description=description,
                                    json_config=json_config
                                )
                            
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'Запись #{i}: Создано задание {task_id} для лаборатории {lab_slug}'
                                )
                            )
                            stats['tasks_created'] += 1
            
            # Выводим итоговую статистику
            self.stdout.write("\n" + "=" * 50)
            self.stdout.write("ИТОГОВАЯ СТАТИСТИКА ИМПОРТА:")
            self.stdout.write(f"Обработано записей: {stats['processed']}")
            self.stdout.write("\nЗАДАНИЯ (LabTask):")
            self.stdout.write(f"  Создано: {stats['tasks_created']}")
            self.stdout.write(f"  Обновлено: {stats['tasks_updated']}")
            self.stdout.write(f"  Пропущено: {stats['tasks_skipped']}")
            self.stdout.write("\nУРОВНИ (LabLevel):")
            self.stdout.write(f"  Создано: {stats['levels_created']}")
            self.stdout.write(f"  Обновлено: {stats['levels_updated']}")
            self.stdout.write(f"  Пропущено: {stats['levels_skipped']}")
            self.stdout.write(f"\nОшибок: {stats['errors']}")
            self.stdout.write(f"Лабораторных работ не найдено: {stats['missing_labs']}")
            self.stdout.write("=" * 50)
            
            if dry_run:
                self.stdout.write(
                    self.style.WARNING('Это был режим DRY RUN - никаких изменений не было внесено')
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS('Импорт завершен успешно!')
                )
                
        except json.JSONDecodeError as e:
            self.stdout.write(
                self.style.ERROR(f'Ошибка парсинга JSON: {str(e)}')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Критическая ошибка: {str(e)}')
            )
            raise


