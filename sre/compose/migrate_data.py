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

def init_django():
    """Инициализирует Django после установки переменных окружения"""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Cyberpolygon.settings')
    import django
    django.setup()

def disconnect_signals():
    """Отключает сигналы post_save и m2m_changed для предотвращения побочных эффектов при загрузке данных"""
    from django.db.models.signals import post_save, m2m_changed
    from interface.models import Competition2User, TeamCompetition2Team
    
    print("🔇 Отключаю сигналы post_save и m2m_changed...")
    
    # Отключаем post_save сигналы (игнорируем ошибки, если сигналы уже отключены)
    try:
        post_save.disconnect(Competition2User.post_create, sender=Competition2User)
    except (KeyError, TypeError):
        pass  # Сигнал уже отключен или не был подключен
    
    try:
        post_save.disconnect(TeamCompetition2Team.post_create, sender=TeamCompetition2Team)
    except (KeyError, TypeError):
        pass
    
    # Отключаем m2m_changed сигналы
    try:
        m2m_changed.disconnect(Competition2User.tasks_changed, sender=Competition2User.tasks.through)
    except (KeyError, TypeError):
        pass
    
    try:
        m2m_changed.disconnect(TeamCompetition2Team.tasks_changed, sender=TeamCompetition2Team.tasks.through)
    except (KeyError, TypeError):
        pass
    
    print("✅ Сигналы отключены")

def reconnect_signals():
    """Включает обратно сигналы post_save и m2m_changed"""
    from django.db.models.signals import post_save, m2m_changed
    from interface.models import Competition2User, TeamCompetition2Team
    
    print("🔊 Включаю обратно сигналы post_save и m2m_changed...")
    
    # Включаем обратно post_save сигналы (отключаем перед подключением, если уже подключены)
    try:
        post_save.disconnect(Competition2User.post_create, sender=Competition2User)
    except (KeyError, TypeError):
        pass
    post_save.connect(Competition2User.post_create, sender=Competition2User)
    
    try:
        post_save.disconnect(TeamCompetition2Team.post_create, sender=TeamCompetition2Team)
    except (KeyError, TypeError):
        pass
    post_save.connect(TeamCompetition2Team.post_create, sender=TeamCompetition2Team)
    
    # Включаем обратно m2m_changed сигналы
    try:
        m2m_changed.disconnect(Competition2User.tasks_changed, sender=Competition2User.tasks.through)
    except (KeyError, TypeError):
        pass
    m2m_changed.connect(Competition2User.tasks_changed, sender=Competition2User.tasks.through)
    
    try:
        m2m_changed.disconnect(TeamCompetition2Team.tasks_changed, sender=TeamCompetition2Team.tasks.through)
    except (KeyError, TypeError):
        pass
    m2m_changed.connect(TeamCompetition2Team.tasks_changed, sender=TeamCompetition2Team.tasks.through)
    
    print("✅ Сигналы включены")

def load_data_direct(dump_file):
    """Загружает данные напрямую через Django call_command (в том же процессе)"""
    from django.core.management import call_command
    
    print(f"📥 Загружаю данные из {dump_file.name}...")
    try:
        call_command('loaddata', str(dump_file), verbosity=1)
        print("✅ Данные успешно загружены")
        return True
    except Exception as e:
        print(f"❌ Ошибка при загрузке данных: {e}")
        return False

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
        
        # Инициализируем Django с настройками PostgreSQL
        init_django()
        
        # 2. Применяем миграции в PostgreSQL
        print("\n🔄 Применяю миграции в PostgreSQL...")
        if not run_command("python manage.py migrate", cwd=project_root):
            print("❌ Ошибка при применении миграций!")
            return
        
        # 3. Отключаем сигналы перед загрузкой данных
        disconnect_signals()
        
        try:
            # 4. Загружаем данные в PostgreSQL напрямую через Django API
            print("\n📥 Загружаю данные в PostgreSQL...")
            if not load_data_direct(dump_file):
                print("❌ Ошибка при загрузке данных!")
                return
        finally:
            # 5. Включаем обратно сигналы после загрузки данных
            reconnect_signals()
        
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
