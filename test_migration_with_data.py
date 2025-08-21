#!/usr/bin/env python
"""
Скрипт для тестирования миграций с реальными данными.
"""

import os
import sys
import django
import json
from django.core.management import execute_from_command_line
from django.core.management.base import CommandError


def export_data_from_sqlite():
    """Экспортирует данные из SQLite"""
    print("📤 Экспорт данных из SQLite...")
    
    try:
        # Устанавливаем SQLite
        os.environ['USE_POSTGRES'] = 'no'
        
        # Экспортируем данные
        execute_from_command_line(['manage.py', 'dumpdata', 'interface.Lab', '--indent', '2', '-o', 'temp_lab_data.json'])
        print("✅ Данные экспортированы в temp_lab_data.json")
        return True
    except Exception as e:
        print(f"❌ Ошибка при экспорте данных: {e}")
        return False


def test_migrations_with_data():
    """Тестирует миграции с реальными данными"""
    print("🔍 Тестирование миграций с данными...")
    
    try:
        # Устанавливаем PostgreSQL
        os.environ['USE_POSTGRES'] = 'yes'
        
        # Применяем миграции
        print("📋 Применение миграций...")
        execute_from_command_line(['manage.py', 'migrate'])
        print("✅ Миграции применены")
        
        # Загружаем данные
        print("📥 Загрузка данных...")
        execute_from_command_line(['manage.py', 'loaddata', 'temp_lab_data.json'])
        print("✅ Данные загружены")
        
        # Проверяем данные
        print("🔍 Проверка данных...")
        execute_from_command_line(['manage.py', 'shell', '-c', 
                                 'from interface.models import Lab; print(f"Загружено {Lab.objects.count()} записей")'])
        print("✅ Данные проверены")
        
        return True
    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        return False


def cleanup_temp_files():
    """Удаляет временные файлы"""
    try:
        if os.path.exists('temp_lab_data.json'):
            os.remove('temp_lab_data.json')
            print("🧹 Временный файл удален")
    except Exception as e:
        print(f"⚠️ Ошибка при удалении временного файла: {e}")


def main():
    """Основная функция тестирования"""
    print("🚀 Запуск тестирования миграций с данными")
    print("=" * 50)
    
    # Настраиваем Django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Cyberpolygon.settings')
    django.setup()
    
    try:
        # Экспортируем данные из SQLite
        if not export_data_from_sqlite():
            return 1
        
        # Тестируем миграции с данными
        if not test_migrations_with_data():
            return 1
        
        print("\n" + "=" * 50)
        print("🎉 Тестирование завершено успешно!")
        print("✅ Миграции работают корректно с данными")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        return 1
    
    finally:
        cleanup_temp_files()


if __name__ == '__main__':
    sys.exit(main())
