#!/usr/bin/env python
"""
Скрипт для тестирования совместимости миграций с разными базами данных.
"""

import os
import sys
import django
from django.conf import settings
from django.core.management import execute_from_command_line


def test_sqlite_migrations():
    """Тестирует миграции с SQLite"""
    print("🔍 Тестирование миграций с SQLite...")
    
    # Устанавливаем переменную окружения для SQLite
    os.environ['USE_POSTGRES'] = 'no'
    
    try:
        # Проверяем план миграций
        execute_from_command_line(['manage.py', 'migrate', '--plan'])
        print("✅ План миграций для SQLite успешно сгенерирован")
        
        # Применяем миграции
        execute_from_command_line(['manage.py', 'migrate'])
        print("✅ Миграции для SQLite успешно применены")
        
        return True
    except Exception as e:
        print(f"❌ Ошибка при тестировании SQLite: {e}")
        return False


def test_postgresql_migrations():
    """Тестирует миграции с PostgreSQL"""
    print("🔍 Тестирование миграций с PostgreSQL...")
    
    # Устанавливаем переменную окружения для PostgreSQL
    os.environ['USE_POSTGRES'] = 'yes'
    
    try:
        # Проверяем план миграций
        execute_from_command_line(['manage.py', 'migrate', '--plan'])
        print("✅ План миграций для PostgreSQL успешно сгенерирован")
        
        # Применяем миграции
        execute_from_command_line(['manage.py', 'migrate'])
        print("✅ Миграции для PostgreSQL успешно применены")
        
        return True
    except Exception as e:
        print(f"❌ Ошибка при тестировании PostgreSQL: {e}")
        return False


def test_database_type_detection():
    """Тестирует определение типа базы данных"""
    print("🔍 Тестирование определения типа базы данных...")
    
    try:
        # Импортируем функцию после настройки Django
        from interface.utils import get_database_type
        
        # Тест для SQLite
        os.environ['USE_POSTGRES'] = 'no'
        django.setup()
        sqlite_type = get_database_type()
        print(f"✅ SQLite тип определен как: {sqlite_type}")
        
        # Тест для PostgreSQL
        os.environ['USE_POSTGRES'] = 'yes'
        django.setup()
        postgresql_type = get_database_type()
        print(f"✅ PostgreSQL тип определен как: {postgresql_type}")
        
        return True
    except Exception as e:
        print(f"❌ Ошибка при тестировании определения типа БД: {e}")
        return False


def main():
    """Основная функция тестирования"""
    print("🚀 Запуск тестирования совместимости миграций")
    print("=" * 50)
    
    # Настраиваем Django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Cyberpolygon.settings')
    django.setup()
    
    results = []
    
    # Тестируем определение типа базы данных
    results.append(test_database_type_detection())
    
    # Тестируем миграции SQLite
    results.append(test_sqlite_migrations())
    
    # Тестируем миграции PostgreSQL
    results.append(test_postgresql_migrations())
    
    # Выводим итоговый результат
    print("\n" + "=" * 50)
    print("📊 Результаты тестирования:")
    
    if all(results):
        print("🎉 Все тесты прошли успешно!")
        print("✅ Миграции совместимы с обеими базами данных")
        return 0
    else:
        print("⚠️  Некоторые тесты не прошли")
        print("❌ Требуется дополнительная отладка")
        return 1


if __name__ == '__main__':
    sys.exit(main())
