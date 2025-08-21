# Generated manually to fix FOREIGN KEY constraint issue

from django.db import migrations
from interface.utils import get_database_type


def get_sql_for_labtask():
    """Возвращает SQL в зависимости от типа базы данных"""
    db_type = get_database_type()
    
    if db_type == 'sqlite':
        return """
        CREATE TABLE interface_labtask_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT,
            lab_id INTEGER NOT NULL,
            task_id varchar(255)
        );
        INSERT INTO interface_labtask_new (id, description, lab_id, task_id)
        SELECT id, description, CAST(lab_id AS INTEGER), task_id
        FROM interface_labtask;
        DROP TABLE interface_labtask;
        ALTER TABLE interface_labtask_new RENAME TO interface_labtask;
        """
    else:  # postgresql
        return """
        -- Создаем новую таблицу
        CREATE TABLE interface_labtask_new (
            id SERIAL PRIMARY KEY,
            description TEXT,
            lab_id INTEGER NOT NULL,
            task_id varchar(255)
        );
        
        -- Копируем данные
        INSERT INTO interface_labtask_new (id, description, lab_id, task_id)
        SELECT id, description, CAST(lab_id AS INTEGER), task_id
        FROM interface_labtask;
        
        -- Удаляем старую таблицу с CASCADE для удаления зависимостей
        DROP TABLE interface_labtask CASCADE;
        
        -- Переименовываем новую таблицу
        ALTER TABLE interface_labtask_new RENAME TO interface_labtask;
        
        -- Восстанавливаем последовательность для SERIAL
        SELECT setval(pg_get_serial_sequence('interface_labtask', 'id'), 
                     (SELECT MAX(id) FROM interface_labtask));
        """


def get_reverse_sql_for_labtask():
    """Возвращает обратный SQL в зависимости от типа базы данных"""
    db_type = get_database_type()
    
    if db_type == 'sqlite':
        return """
        CREATE TABLE interface_labtask_old (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT,
            lab_id varchar(255) NOT NULL,
            task_id varchar(255)
        );
        INSERT INTO interface_labtask_old (id, description, lab_id, task_id)
        SELECT id, description, CAST(lab_id AS varchar), task_id
        FROM interface_labtask;
        DROP TABLE interface_labtask;
        ALTER TABLE interface_labtask_old RENAME TO interface_labtask;
        """
    else:  # postgresql
        return """
        -- Создаем старую таблицу
        CREATE TABLE interface_labtask_old (
            id SERIAL PRIMARY KEY,
            description TEXT,
            lab_id varchar(255) NOT NULL,
            task_id varchar(255)
        );
        
        -- Копируем данные обратно
        INSERT INTO interface_labtask_old (id, description, lab_id, task_id)
        SELECT id, description, CAST(lab_id AS varchar), task_id
        FROM interface_labtask;
        
        -- Удаляем новую таблицу с CASCADE
        DROP TABLE interface_labtask CASCADE;
        
        -- Переименовываем старую таблицу
        ALTER TABLE interface_labtask_old RENAME TO interface_labtask;
        
        -- Восстанавливаем последовательность
        SELECT setval(pg_get_serial_sequence('interface_labtask', 'id'), 
                     (SELECT MAX(id) FROM interface_labtask));
        """


class Migration(migrations.Migration):

    dependencies = [
        ('interface', '0025_auto_20250731_2243'),
    ]

    operations = [
        migrations.RunSQL(
            # SQL для изменения типа поля lab_id с varchar на INTEGER
            sql=get_sql_for_labtask(),
            reverse_sql=get_reverse_sql_for_labtask()
        ),
    ] 