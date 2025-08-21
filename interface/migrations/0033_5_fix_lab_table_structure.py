# Generated manually to fix Lab table structure for both SQLite and PostgreSQL

from django.db import migrations
from interface.utils import get_database_type


def get_sql_for_lab_structure():
    """Возвращает SQL для исправления структуры таблицы Lab"""
    db_type = get_database_type()
    
    if db_type == 'sqlite':
        return """
        -- В SQLite нельзя добавить PRIMARY KEY через ALTER TABLE
        -- Поэтому просто добавляем поле id без PRIMARY KEY
        ALTER TABLE interface_lab ADD COLUMN id INTEGER;
        
        -- Обновляем id для существующих записей
        UPDATE interface_lab SET id = rowid;
        """
    else:  # postgresql
        return """
        -- Создаем новую таблицу Lab с правильной структурой
        CREATE TABLE interface_lab_new (
            id SERIAL PRIMARY KEY,
            name varchar(255) NOT NULL,
            description text NOT NULL,
            answer_flag varchar(1024),
            slug varchar(255) NOT NULL,
            platform varchar(3) NOT NULL,
            program varchar(32) NOT NULL,
            icon varchar(50) NOT NULL,
            "NodesData" jsonb NOT NULL,
            "ConnectorsData" jsonb NOT NULL,
            "Connectors2CloudData" jsonb NOT NULL,
            "NetworksData" jsonb NOT NULL
        );
        
        -- Копируем данные из старой таблицы (исключаем так как SERIAL автоматически генерирует)
        INSERT INTO interface_lab_new (
            name, description, answer_flag, slug, platform, program, icon,
            "NodesData", "ConnectorsData", "Connectors2CloudData", "NetworksData"
        )
        SELECT 
            name, description, answer_flag, slug, platform, program, icon,
            "NodesData", "ConnectorsData", "Connectors2CloudData", "NetworksData"
        FROM interface_lab;
        
        -- Удаляем старую таблицу с CASCADE
        DROP TABLE interface_lab CASCADE;
        
        -- Переименовываем новую таблицу
        ALTER TABLE interface_lab_new RENAME TO interface_lab;
        
        -- Восстанавливаем последовательность
        SELECT setval(pg_get_serial_sequence('interface_lab', 'id'), 
                     (SELECT MAX(id) FROM interface_lab));
        """


def get_reverse_sql_for_lab_structure():
    """Возвращает SQL для отката изменений структуры таблицы Lab"""
    db_type = get_database_type()
    
    if db_type == 'sqlite':
        return """
        -- Удаляем поле id из таблицы Lab
        ALTER TABLE interface_lab DROP COLUMN id;
        """
    else:  # postgresql
        return """
        -- Создаем старую таблицу Lab
        CREATE TABLE interface_lab_old (
            id SERIAL PRIMARY KEY,
            name varchar(255) NOT NULL,
            description text NOT NULL,
            answer_flag varchar(1024),
            slug varchar(255) NOT NULL,
            platform varchar(3) NOT NULL,
            program varchar(32) NOT NULL,
            icon varchar(50) NOT NULL,
            "NodesData" jsonb NOT NULL,
            "ConnectorsData" jsonb NOT NULL,
            "Connectors2CloudData" jsonb NOT NULL,
            "NetworksData" jsonb NOT NULL
        );
        
        -- Копируем данные обратно (исключаем так как SERIAL автоматически генерирует)
        INSERT INTO interface_lab_old (
            name, description, answer_flag, slug, platform, program, icon,
            "NodesData", "ConnectorsData", "Connectors2CloudData", "NetworksData"
        )
        SELECT 
            name, description, answer_flag, slug, platform, program, icon,
            "NodesData", "ConnectorsData", "Connectors2CloudData", "NetworksData"
        FROM interface_lab;
        
        -- Удаляем новую таблицу с CASCADE
        DROP TABLE interface_lab CASCADE;
        
        -- Переименовываем старую таблицу
        ALTER TABLE interface_lab_old RENAME TO interface_lab;
        
        -- Восстанавливаем последовательность
        SELECT setval(pg_get_serial_sequence('interface_lab', 'id'), 
                     (SELECT MAX(id) FROM interface_lab));
        """


class Migration(migrations.Migration):

    dependencies = [
        ('interface', '0032_cleanup_orphaned_records'),
    ]

    operations = [
        migrations.RunSQL(
            sql=get_sql_for_lab_structure(),
            reverse_sql=get_reverse_sql_for_lab_structure()
        ),
    ]
