"""
Утилиты для создания универсальных миграций, работающих с разными базами данных.
"""

from django.db import migrations
from interface.utils import get_database_type


class DatabaseAwareMigration(migrations.Migration):
    """
    Базовый класс для миграций, которые должны работать с разными базами данных.
    Автоматически определяет тип базы данных и применяет соответствующий SQL.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.db_type = get_database_type()
    
    def get_sql_for_db(self, sqlite_sql, postgresql_sql):
        """
        Возвращает SQL в зависимости от типа базы данных.
        
        Args:
            sqlite_sql: SQL для SQLite
            postgresql_sql: SQL для PostgreSQL
            
        Returns:
            str: SQL для текущей базы данных
        """
        if self.db_type == 'sqlite':
            return sqlite_sql
        elif self.db_type == 'postgresql':
            return postgresql_sql
        else:
            raise ValueError(f"Неподдерживаемый тип базы данных: {self.db_type}")
    
    def create_database_specific_operation(self, sqlite_sql, postgresql_sql, 
                                         sqlite_reverse_sql=None, postgresql_reverse_sql=None):
        """
        Создает операцию RunSQL с SQL, специфичным для базы данных.
        
        Args:
            sqlite_sql: SQL для SQLite
            postgresql_sql: SQL для PostgreSQL
            sqlite_reverse_sql: Обратный SQL для SQLite (опционально)
            postgresql_reverse_sql: Обратный SQL для PostgreSQL (опционально)
            
        Returns:
            migrations.RunSQL: Операция миграции
        """
        sql = self.get_sql_for_db(sqlite_sql, postgresql_sql)
        
        if sqlite_reverse_sql and postgresql_reverse_sql:
            reverse_sql = self.get_sql_for_db(sqlite_reverse_sql, postgresql_reverse_sql)
        else:
            reverse_sql = None
            
        return migrations.RunSQL(sql=sql, reverse_sql=reverse_sql)


def create_table_sql(table_name, columns, db_type):
    """
    Создает SQL для создания таблицы в зависимости от типа базы данных.
    
    Args:
        table_name: Имя таблицы
        columns: Список колонок в формате (name, type, constraints)
        db_type: Тип базы данных ('sqlite' или 'postgresql')
        
    Returns:
        str: SQL для создания таблицы
    """
    if db_type == 'sqlite':
        # SQLite использует INTEGER PRIMARY KEY AUTOINCREMENT
        column_defs = []
        for name, type_def, constraints in columns:
            if 'PRIMARY KEY' in constraints and 'AUTOINCREMENT' not in constraints:
                constraints = constraints.replace('PRIMARY KEY', 'PRIMARY KEY AUTOINCREMENT')
            column_defs.append(f"{name} {type_def} {constraints}".strip())
        
        return f"CREATE TABLE {table_name} (\n    " + ",\n    ".join(column_defs) + "\n);"
    
    elif db_type == 'postgresql':
        # PostgreSQL использует SERIAL для автоинкрементных полей
        column_defs = []
        for name, type_def, constraints in columns:
            if 'INTEGER PRIMARY KEY' in type_def and 'AUTOINCREMENT' in constraints:
                # Заменяем INTEGER PRIMARY KEY AUTOINCREMENT на SERIAL PRIMARY KEY
                column_defs.append(f"{name} SERIAL PRIMARY KEY")
            else:
                # Убираем AUTOINCREMENT из constraints для PostgreSQL
                constraints = constraints.replace('AUTOINCREMENT', '').strip()
                column_defs.append(f"{name} {type_def} {constraints}".strip())
        
        return f"CREATE TABLE {table_name} (\n    " + ",\n    ".join(column_defs) + "\n);"
    
    else:
        raise ValueError(f"Неподдерживаемый тип базы данных: {db_type}")


def get_common_sql_operations():
    """
    Возвращает словарь с общими SQL операциями для разных баз данных.
    
    Returns:
        dict: Словарь с SQL операциями
    """
    return {
        'sqlite': {
            'integer_primary_key': 'INTEGER PRIMARY KEY AUTOINCREMENT',
            'datetime_type': 'datetime',
            'boolean_type': 'bool',
            'unsigned_integer': 'integer unsigned',
        },
        'postgresql': {
            'integer_primary_key': 'SERIAL PRIMARY KEY',
            'datetime_type': 'timestamp',
            'boolean_type': 'boolean',
            'unsigned_integer': 'integer',
        }
    }
