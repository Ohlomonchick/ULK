import json
import os
from django.core.management.base import BaseCommand
from interface.models import LabTask, Lab, LabLevel


class Command(BaseCommand):
    help = 'Экспортирует все LabTask и LabLevel в JSON файл с параметрами task_id, description, level_number и slug лабораторной работы'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            default='labtasks_export.json',
            help='Путь к выходному JSON файлу (по умолчанию: labtasks_export.json)'
        )
        parser.add_argument(
            '--format',
            choices=['json', 'txt'],
            default='json',
            help='Формат выходного файла (json или txt)'
        )

    def handle(self, *args, **options):
        output_file = options['output']
        output_format = options['format']
        
        # Получаем все LabTask и LabLevel с связанными Lab
        lab_tasks = LabTask.objects.select_related('lab').all()
        lab_levels = LabLevel.objects.select_related('lab').all()
        
        if not lab_tasks.exists() and not lab_levels.exists():
            self.stdout.write(
                self.style.WARNING('LabTask и LabLevel не найдены в базе данных')
            )
            return
        
        # Формируем данные для экспорта
        export_data = {
            'lab_tasks': [],
            'lab_levels': []
        }
        
        # Экспортируем LabTask
        for task in lab_tasks:
            task_data = {
                'task_id': task.task_id,
                'description': task.description,
                'lab_slug': task.lab.slug,
                'lab_name': task.lab.name,  # Дополнительная информация для удобства
                'json_config': task.json_config or {},  # Включаем конфигурацию
            }
            export_data['lab_tasks'].append(task_data)
        
        # Экспортируем LabLevel
        for level in lab_levels:
            level_data = {
                'level_number': level.level_number,
                'description': level.description,
                'lab_slug': level.lab.slug,
                'lab_name': level.lab.name,  # Дополнительная информация для удобства
            }
            export_data['lab_levels'].append(level_data)
        
        # Создаем директорию если не существует
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        try:
            if output_format == 'json':
                # Записываем в JSON формате
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, ensure_ascii=False, indent=2)
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Успешно экспортировано {len(export_data["lab_tasks"])} LabTask и {len(export_data["lab_levels"])} LabLevel в файл {output_file}'
                    )
                )
                
            elif output_format == 'txt':
                # Записываем в текстовом формате
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(f"Экспорт LabTask и LabLevel\n")
                    f.write(f"LabTask - всего записей: {len(export_data['lab_tasks'])}\n")
                    f.write(f"LabLevel - всего записей: {len(export_data['lab_levels'])}\n")
                    f.write("=" * 80 + "\n\n")
                    
                    # Экспорт LabTask
                    f.write("LAB TASKS:\n")
                    f.write("=" * 40 + "\n")
                    for i, task_data in enumerate(export_data['lab_tasks'], 1):
                        f.write(f"Задание #{i}:\n")
                        f.write(f"  Task ID: {task_data['task_id']}\n")
                        f.write(f"  Описание: {task_data['description']}\n")
                        f.write(f"  Lab Slug: {task_data['lab_slug']}\n")
                        f.write(f"  Lab Name: {task_data['lab_name']}\n")
                        f.write("-" * 40 + "\n\n")
                    
                    # Экспорт LabLevel
                    f.write("\nLAB LEVELS:\n")
                    f.write("=" * 40 + "\n")
                    for i, level_data in enumerate(export_data['lab_levels'], 1):
                        f.write(f"Вариант #{i}:\n")
                        f.write(f"  Level Number: {level_data['level_number']}\n")
                        f.write(f"  Описание: {level_data['description']}\n")
                        f.write(f"  Lab Slug: {level_data['lab_slug']}\n")
                        f.write(f"  Lab Name: {level_data['lab_name']}\n")
                        f.write("-" * 40 + "\n\n")
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Успешно экспортировано {len(export_data["lab_tasks"])} LabTask и {len(export_data["lab_levels"])} LabLevel в текстовый файл {output_file}'
                    )
                )
            
            # Выводим статистику
            self.stdout.write("\nСтатистика экспорта:")
            self.stdout.write(f"Всего LabTask: {len(export_data['lab_tasks'])}")
            self.stdout.write(f"Всего LabLevel: {len(export_data['lab_levels'])}")
            
            # Группируем по лабораторным работам
            lab_task_stats = {}
            lab_level_stats = {}
            
            for task_data in export_data['lab_tasks']:
                lab_slug = task_data['lab_slug']
                if lab_slug not in lab_task_stats:
                    lab_task_stats[lab_slug] = 0
                lab_task_stats[lab_slug] += 1
            
            for level_data in export_data['lab_levels']:
                lab_slug = level_data['lab_slug']
                if lab_slug not in lab_level_stats:
                    lab_level_stats[lab_slug] = 0
                lab_level_stats[lab_slug] += 1
            
            # Объединяем все лабораторные работы
            all_labs = set(lab_task_stats.keys()) | set(lab_level_stats.keys())
            
            self.stdout.write(f"Лабораторных работ: {len(all_labs)}")
            for lab_slug in sorted(all_labs):
                task_count = lab_task_stats.get(lab_slug, 0)
                level_count = lab_level_stats.get(lab_slug, 0)
                self.stdout.write(f"  - {lab_slug}: {task_count} заданий, {level_count} вариантов")
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Ошибка при записи файла: {str(e)}')
            )
            raise

