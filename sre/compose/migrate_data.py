#!/usr/bin/env python3
"""
Скрипт для миграции данных из SQLite в PostgreSQL
Использует настройки из env.example
"""

import os
import sys
import subprocess
import json
from pathlib import Path

# Добавляем корневую директорию проекта в Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Настройки из env.example
DB_CONFIG = {
    'POSTGRES_DB': 'cyberpolygon',
    'POSTGRES_USER': 'postgres', 
    'POSTGRES_PASSWORD': 'postgres',
    'POSTGRES_HOST': 'localhost',
    'POSTGRES_PORT': '5431'
}

def set_env_vars():
    """Устанавливаем переменные окружения для PostgreSQL"""
    os.environ['USE_POSTGRES'] = 'yes'
    os.environ['DB_USER'] = DB_CONFIG['POSTGRES_USER']
    os.environ['DB_PASSWORD'] = DB_CONFIG['POSTGRES_PASSWORD']
    os.environ['DB_HOST'] = DB_CONFIG['POSTGRES_HOST']
    os.environ['DB_NAME'] = DB_CONFIG['POSTGRES_DB']
    os.environ['DB_PORT'] = DB_CONFIG['POSTGRES_PORT']
    os.environ['PNET_URL'] = ''

def clear_env_vars():
    """Очищаем переменные окружения для использования SQLite"""
    env_vars = ['USE_POSTGRES', 'DB_USER', 'DB_PASSWORD', 'DB_HOST', 'DB_NAME', 'DB_PORT']
    for var in env_vars:
        if var in os.environ:
            del os.environ[var]

def run_command(cmd, cwd=None):
    """Выполняет команду и возвращает результат"""
    print(f"Выполняю: {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Ошибка: {result.stderr}")
        return False
    print(f"Успешно: {result.stdout}")
    return True

def main():
    print("🚀 Начинаю миграцию данных из SQLite в PostgreSQL...")
    
    # Проверяем существование SQLite базы
    sqlite_db = project_root / 'db.sqlite3'
    if not sqlite_db.exists():
        print("❌ Файл db.sqlite3 не найден!")
        return
    
    print(f"✅ Найден SQLite файл: {sqlite_db}")
    
    # Создаем временный файл для дампа
    dump_file = project_root / 'temp_dump.json'
    
    try:
        # Очищаем переменные окружения для использования SQLite
        clear_env_vars()
        
        # 1. Создаем дамп из SQLite с явным указанием кодировки
        print("\n📤 Создаю дамп данных из SQLite...")
        
        # Для Windows используем chcp для установки UTF-8 кодировки
        if os.name == 'nt':  # Windows
            dump_cmd = f"chcp 65001 > nul && python manage.py dumpdata --exclude auth.permission --exclude contenttypes --indent 2 > {dump_file}"
        else:  # Unix/Linux
            dump_cmd = f"python manage.py dumpdata --exclude auth.permission --exclude contenttypes --indent 2 > {dump_file}"
        
        if not run_command(dump_cmd, cwd=project_root):
            print("❌ Ошибка при создании дампа!")
            return
        
        # Проверяем, что файл дампа создался и не пустой
        if not dump_file.exists():
            print("❌ Файл дампа не был создан!")
            return
        
        file_size = dump_file.stat().st_size
        if file_size == 0:
            print("❌ Файл дампа пустой!")
            return
        
        print(f"✅ Дамп создан: {dump_file} ({file_size} байт)")
        
        # Проверяем и исправляем кодировку файла
        print("\n🔧 Проверяю кодировку файла дампа...")
        try:
            with open(dump_file, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            print("⚠️  Обнаружена проблема с кодировкой, исправляю...")
            # Пробуем разные кодировки
            encodings = ['cp1251', 'latin1', 'iso-8859-1']
            content = None
            
            for encoding in encodings:
                try:
                    with open(dump_file, 'r', encoding=encoding) as f:
                        content = f.read()
                    print(f"✅ Успешно прочитан с кодировкой {encoding}")
                    break
                except UnicodeDecodeError:
                    continue
            
            if content is None:
                print("❌ Не удалось прочитать файл ни с одной кодировкой!")
                return
            
            # Перезаписываем файл в UTF-8
            with open(dump_file, 'w', encoding='utf-8') as f:
                f.write(content)
            print("✅ Файл пересохранен в UTF-8")

        # Устанавливаем переменные окружения для PostgreSQL
        set_env_vars()
        
        # 2. Применяем миграции в PostgreSQL
        print("\n🔄 Применяю миграции в PostgreSQL...")
        if not run_command("python manage.py migrate", cwd=project_root):
            print("❌ Ошибка при применении миграций!")
            return
        
        # 3. Загружаем данные в PostgreSQL
        print("\n📥 Загружаю данные в PostgreSQL...")
        if not run_command(f"python manage.py loaddata {dump_file.name}", cwd=project_root):
            print("❌ Ошибка при загрузке данных!")
            return
        
        print("\n✅ Миграция завершена успешно!")
        print(f"📊 База данных: {DB_CONFIG['POSTGRES_DB']}")
        print(f"👤 Пользователь: {DB_CONFIG['POSTGRES_USER']}")
        print(f"🌐 Хост: {DB_CONFIG['POSTGRES_HOST']}:{DB_CONFIG['POSTGRES_PORT']}")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        # Удаляем временный файл
        if dump_file.exists():
            dump_file.unlink()
            print("🧹 Временный файл удален")

if __name__ == "__main__":
    main()
