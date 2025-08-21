# Совместимость миграций Django с разными базами данных

## Проблема

В проекте возникла ситуация, когда миграции Django работали корректно с SQLite, но падали с ошибкой синтаксиса в PostgreSQL. Основные причины:

1. **Синтаксис AUTOINCREMENT** - SQLite-специфичный синтаксис `AUTOINCREMENT`, который не поддерживается в PostgreSQL
2. **Зависимости внешних ключей** - PostgreSQL не позволяет удалять таблицы, на которые ссылаются внешние ключи, без использования `CASCADE`

## Решение

Создана система универсальных миграций, которая автоматически определяет тип базы данных и применяет соответствующий SQL-код с учетом особенностей каждой СУБД.

### Компоненты решения

#### 1. Утилита определения типа базы данных (`interface/utils.py`)

```python
def get_database_type():
    """
    Определяет тип базы данных на основе настроек Django.
    Возвращает 'sqlite' или 'postgresql'.
    """
    from django.conf import settings
    from django.db import connection
    
    # Проверяем engine базы данных
    engine = settings.DATABASES['default']['ENGINE']
    
    if 'sqlite' in engine:
        return 'sqlite'
    elif 'postgresql' in engine:
        return 'postgresql'
    else:
        # Fallback - определяем по connection
        vendor = connection.vendor
        if vendor == 'sqlite':
            return 'sqlite'
        elif vendor == 'postgresql':
            return 'postgresql'
        else:
            raise ValueError(f"Неподдерживаемый тип базы данных: {vendor}")
```

#### 2. Утилиты для миграций (`interface/migration_utils.py`)

Содержит базовые классы и функции для создания универсальных миграций:

- `DatabaseAwareMigration` - базовый класс для миграций
- `create_table_sql()` - функция для создания SQL создания таблиц
- `get_common_sql_operations()` - словарь с общими SQL операциями

### Основные различия между SQLite и PostgreSQL

| Аспект | SQLite | PostgreSQL |
|--------|--------|------------|
| Автоинкрементные поля | `INTEGER PRIMARY KEY AUTOINCREMENT` | `SERIAL PRIMARY KEY` |
| Тип даты/времени | `datetime` | `timestamp` |
| Булевый тип | `bool` | `boolean` |
| Беззнаковые целые | `integer unsigned` | `integer` |
| Удаление таблиц с зависимостями | `DROP TABLE` | `DROP TABLE CASCADE` |
| Последовательности | Автоматические | Требуют `setval()` |

### Особенности PostgreSQL

#### 1. Обработка зависимостей

В PostgreSQL при удалении таблицы, на которую ссылаются внешние ключи, необходимо использовать `CASCADE`:

```sql
-- SQLite
DROP TABLE interface_labtask;

-- PostgreSQL
DROP TABLE interface_labtask CASCADE;
```

#### 2. Восстановление последовательностей

После пересоздания таблиц с `SERIAL` полями необходимо восстановить последовательности:

```sql
SELECT setval(pg_get_serial_sequence('interface_labtask', 'id'), 
             (SELECT MAX(id) FROM interface_labtask));
```

### Пример использования

```python
from django.db import migrations
from interface.utils import get_database_type

def get_sql_for_table():
    """Возвращает SQL в зависимости от типа базы данных"""
    db_type = get_database_type()
    
    if db_type == 'sqlite':
        return """
        CREATE TABLE example_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name varchar(255) NOT NULL
        );
        INSERT INTO example_new (id, name)
        SELECT id, name FROM example;
        DROP TABLE example;
        ALTER TABLE example_new RENAME TO example;
        """
    else:  # postgresql
        return """
        -- Создаем новую таблицу
        CREATE TABLE example_new (
            id SERIAL PRIMARY KEY,
            name varchar(255) NOT NULL
        );
        
        -- Копируем данные
        INSERT INTO example_new (id, name)
        SELECT id, name FROM example;
        
        -- Удаляем старую таблицу с CASCADE
        DROP TABLE example CASCADE;
        
        -- Переименовываем новую таблицу
        ALTER TABLE example_new RENAME TO example;
        
        -- Восстанавливаем последовательность
        SELECT setval(pg_get_serial_sequence('example', 'id'), 
                     (SELECT MAX(id) FROM example));
        """

class Migration(migrations.Migration):
    operations = [
        migrations.RunSQL(
            sql=get_sql_for_table(),
            reverse_sql=get_reverse_sql_for_table()
        ),
    ]
```

### Настройка окружения

Тип базы данных определяется переменной окружения `USE_POSTGRES`:

- `USE_POSTGRES=yes` - использует PostgreSQL
- `USE_POSTGRES` не установлена или любое другое значение - использует SQLite

### Преимущества решения

1. **Автоматическое определение** - не требует ручного указания типа БД
2. **Обратная совместимость** - работает с существующими миграциями
3. **Масштабируемость** - легко добавить поддержку других БД
4. **Читаемость** - код остается понятным и структурированным
5. **Безопасность** - правильно обрабатывает зависимости в PostgreSQL

### Рекомендации для будущих миграций

1. Используйте функцию `get_database_type()` для определения типа БД
2. Создавайте отдельные SQL-шаблоны для каждого типа БД
3. Для PostgreSQL всегда используйте `DROP TABLE CASCADE` при удалении таблиц с зависимостями
4. Восстанавливайте последовательности после пересоздания таблиц с `SERIAL` полями
5. Тестируйте миграции на обеих базах данных
6. Документируйте специфичные для БД особенности

### Тестирование

Для тестирования миграций:

```bash
# Тест с SQLite
python manage.py migrate

# Тест с PostgreSQL
USE_POSTGRES=yes python manage.py migrate
```

### Устранение неполадок

#### Ошибка "cannot drop table because other objects depend on it"

**Причина**: В PostgreSQL таблица имеет зависимости (внешние ключи).

**Решение**: Используйте `DROP TABLE CASCADE` вместо `DROP TABLE`.

#### Ошибка "syntax error at or near AUTOINCREMENT"

**Причина**: Использование SQLite-специфичного синтаксиса в PostgreSQL.

**Решение**: Замените `INTEGER PRIMARY KEY AUTOINCREMENT` на `SERIAL PRIMARY KEY`.

#### Ошибка "sequence does not exist"

**Причина**: После пересоздания таблицы с `SERIAL` полем последовательность не восстановлена.

**Решение**: Добавьте восстановление последовательности:

```sql
SELECT setval(pg_get_serial_sequence('table_name', 'id'), 
             (SELECT MAX(id) FROM table_name));
```

### Известные ограничения

1. Миграции должны выполняться в правильном порядке из-за зависимостей
2. При откате миграций в PostgreSQL могут потребоваться дополнительные операции
3. Некоторые сложные SQL операции могут требовать специфичной обработки для каждой БД
