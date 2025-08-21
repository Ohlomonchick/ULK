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
        -- Добавляем поле id к существующей таблице Lab
        ALTER TABLE interface_lab ADD COLUMN id SERIAL PRIMARY KEY;
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
        -- Удаляем поле id из таблицы Lab
        ALTER TABLE interface_lab DROP COLUMN id;
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
