# Generated manually to fix all FOREIGN KEY constraints referencing Lab

from django.db import migrations
from interface.utils import get_database_type


def get_sql_for_table(table_name):
    """Возвращает SQL для конкретной таблицы в зависимости от типа базы данных"""
    db_type = get_database_type()
    
    if db_type == 'sqlite':
        sql_templates = {
            'lablevel': """
            CREATE TABLE interface_lablevel_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level_number integer unsigned NOT NULL,
                description TEXT NOT NULL,
                lab_id INTEGER NOT NULL
            );
            INSERT INTO interface_lablevel_new (id, level_number, description, lab_id)
            SELECT id, level_number, description, CAST(lab_id AS INTEGER)
            FROM interface_lablevel;
            DROP TABLE interface_lablevel;
            ALTER TABLE interface_lablevel_new RENAME TO interface_lablevel;
            """,
            'answers': """
            CREATE TABLE interface_answers_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                datetime datetime,
                user_id bigint,
                lab_id INTEGER NOT NULL,
                lab_task_id bigint,
                team_id bigint
            );
            INSERT INTO interface_answers_new (id, datetime, user_id, lab_id, lab_task_id, team_id)
            SELECT id, datetime, user_id, CAST(lab_id AS INTEGER), lab_task_id, team_id
            FROM interface_answers;
            DROP TABLE interface_answers;
            ALTER TABLE interface_answers_new RENAME TO interface_answers;
            """,
            'kkzlab': """
            CREATE TABLE interface_kkzlab_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                num_tasks integer unsigned NOT NULL,
                kkz_id bigint NOT NULL,
                lab_id INTEGER NOT NULL
            );
            INSERT INTO interface_kkzlab_new (id, num_tasks, kkz_id, lab_id)
            SELECT id, num_tasks, kkz_id, CAST(lab_id AS INTEGER)
            FROM interface_kkzlab;
            DROP TABLE interface_kkzlab;
            ALTER TABLE interface_kkzlab_new RENAME TO interface_kkzlab;
            """,
            'competition': """
            CREATE TABLE interface_competition_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug varchar(255) NOT NULL,
                start datetime NOT NULL,
                finish datetime NOT NULL,
                participants INTEGER,
                lab_id INTEGER,
                level_id bigint,
                deleted bool NOT NULL,
                kkz_id bigint,
                num_tasks integer unsigned NOT NULL
            );
            INSERT INTO interface_competition_new (id, slug, start, finish, participants, lab_id, level_id, deleted, kkz_id, num_tasks)
            SELECT id, slug, start, finish, participants, CAST(lab_id AS INTEGER), level_id, deleted, kkz_id, num_tasks
            FROM interface_competition;
            DROP TABLE interface_competition;
            ALTER TABLE interface_competition_new RENAME TO interface_competition;
            """
        }
    else:  # postgresql
        sql_templates = {
            'lablevel': """
            -- Создаем новую таблицу
            CREATE TABLE interface_lablevel_new (
                id SERIAL PRIMARY KEY,
                level_number integer NOT NULL,
                description TEXT NOT NULL,
                lab_id INTEGER NOT NULL
            );
            
            -- Копируем данные
            INSERT INTO interface_lablevel_new (id, level_number, description, lab_id)
            SELECT id, level_number, description, CAST(lab_id AS INTEGER)
            FROM interface_lablevel;
            
            -- Удаляем старую таблицу с CASCADE
            DROP TABLE interface_lablevel CASCADE;
            
            -- Переименовываем новую таблицу
            ALTER TABLE interface_lablevel_new RENAME TO interface_lablevel;
            
            -- Восстанавливаем последовательность
            SELECT setval(pg_get_serial_sequence('interface_lablevel', 'id'), 
                         (SELECT MAX(id) FROM interface_lablevel));
            """,
            'answers': """
            -- Создаем новую таблицу
            CREATE TABLE interface_answers_new (
                id SERIAL PRIMARY KEY,
                datetime timestamp,
                user_id bigint,
                lab_id INTEGER NOT NULL,
                lab_task_id bigint,
                team_id bigint
            );
            
            -- Копируем данные
            INSERT INTO interface_answers_new (id, datetime, user_id, lab_id, lab_task_id, team_id)
            SELECT id, datetime, user_id, CAST(lab_id AS INTEGER), lab_task_id, team_id
            FROM interface_answers;
            
            -- Удаляем старую таблицу с CASCADE
            DROP TABLE interface_answers CASCADE;
            
            -- Переименовываем новую таблицу
            ALTER TABLE interface_answers_new RENAME TO interface_answers;
            
            -- Восстанавливаем последовательность
            SELECT setval(pg_get_serial_sequence('interface_answers', 'id'), 
                         (SELECT MAX(id) FROM interface_answers));
            """,
            'kkzlab': """
            -- Создаем новую таблицу
            CREATE TABLE interface_kkzlab_new (
                id SERIAL PRIMARY KEY,
                num_tasks integer NOT NULL,
                kkz_id bigint NOT NULL,
                lab_id INTEGER NOT NULL
            );
            
            -- Копируем данные
            INSERT INTO interface_kkzlab_new (id, num_tasks, kkz_id, lab_id)
            SELECT id, num_tasks, kkz_id, CAST(lab_id AS INTEGER)
            FROM interface_kkzlab;
            
            -- Удаляем старую таблицу с CASCADE
            DROP TABLE interface_kkzlab CASCADE;
            
            -- Переименовываем новую таблицу
            ALTER TABLE interface_kkzlab_new RENAME TO interface_kkzlab;
            
            -- Восстанавливаем последовательность
            SELECT setval(pg_get_serial_sequence('interface_kkzlab', 'id'), 
                         (SELECT MAX(id) FROM interface_kkzlab));
            """,
            'competition': """
            -- Создаем новую таблицу
            CREATE TABLE interface_competition_new (
                id SERIAL PRIMARY KEY,
                slug varchar(255) NOT NULL,
                start timestamp NOT NULL,
                finish timestamp NOT NULL,
                participants INTEGER,
                lab_id INTEGER,
                level_id bigint,
                deleted boolean NOT NULL,
                kkz_id bigint,
                num_tasks integer NOT NULL
            );
            
            -- Копируем данные
            INSERT INTO interface_competition_new (id, slug, start, finish, participants, lab_id, level_id, deleted, kkz_id, num_tasks)
            SELECT id, slug, start, finish, participants, CAST(lab_id AS INTEGER), level_id, deleted, kkz_id, num_tasks
            FROM interface_competition;
            
            -- Удаляем старую таблицу с CASCADE
            DROP TABLE interface_competition CASCADE;
            
            -- Переименовываем новую таблицу
            ALTER TABLE interface_competition_new RENAME TO interface_competition;
            
            -- Восстанавливаем последовательность
            SELECT setval(pg_get_serial_sequence('interface_competition', 'id'), 
                         (SELECT MAX(id) FROM interface_competition));
            """
        }
    
    return sql_templates.get(table_name, "")


def get_reverse_sql_for_table(table_name):
    """Возвращает обратный SQL для конкретной таблицы в зависимости от типа базы данных"""
    db_type = get_database_type()
    
    if db_type == 'sqlite':
        reverse_sql_templates = {
            'lablevel': """
            CREATE TABLE interface_lablevel_old (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level_number integer unsigned NOT NULL,
                description TEXT NOT NULL,
                lab_id varchar(255) NOT NULL
            );
            INSERT INTO interface_lablevel_old (id, level_number, description, lab_id)
            SELECT id, level_number, description, CAST(lab_id AS varchar)
            FROM interface_lablevel;
            DROP TABLE interface_lablevel;
            ALTER TABLE interface_lablevel_old RENAME TO interface_lablevel;
            """,
            'answers': """
            CREATE TABLE interface_answers_old (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                datetime datetime,
                user_id bigint,
                lab_id varchar(255) NOT NULL,
                lab_task_id bigint,
                team_id bigint
            );
            INSERT INTO interface_answers_old (id, datetime, user_id, lab_id, lab_task_id, team_id)
            SELECT id, datetime, user_id, CAST(lab_id AS varchar), lab_task_id, team_id
            FROM interface_answers;
            DROP TABLE interface_answers;
            ALTER TABLE interface_answers_old RENAME TO interface_answers;
            """,
            'kkzlab': """
            CREATE TABLE interface_kkzlab_old (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                num_tasks integer unsigned NOT NULL,
                kkz_id bigint NOT NULL,
                lab_id varchar(255) NOT NULL
            );
            INSERT INTO interface_kkzlab_old (id, num_tasks, kkz_id, lab_id)
            SELECT id, num_tasks, kkz_id, CAST(lab_id AS varchar)
            FROM interface_kkzlab;
            DROP TABLE interface_kkzlab;
            ALTER TABLE interface_kkzlab_old RENAME TO interface_kkzlab;
            """,
            'competition': """
            CREATE TABLE interface_competition_old (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug varchar(255) NOT NULL,
                start datetime NOT NULL,
                finish datetime NOT NULL,
                participants INTEGER,
                lab_id varchar(255),
                level_id bigint,
                deleted bool NOT NULL,
                kkz_id bigint,
                num_tasks integer unsigned NOT NULL
            );
            INSERT INTO interface_competition_old (id, slug, start, finish, participants, lab_id, level_id, deleted, kkz_id, num_tasks)
            SELECT id, slug, start, finish, participants, CAST(lab_id AS varchar), level_id, deleted, kkz_id, num_tasks
            FROM interface_competition;
            DROP TABLE interface_competition;
            ALTER TABLE interface_competition_old RENAME TO interface_competition;
            """
        }
    else:  # postgresql
        reverse_sql_templates = {
            'lablevel': """
            -- Создаем старую таблицу
            CREATE TABLE interface_lablevel_old (
                id SERIAL PRIMARY KEY,
                level_number integer NOT NULL,
                description TEXT NOT NULL,
                lab_id varchar(255) NOT NULL
            );
            
            -- Копируем данные обратно
            INSERT INTO interface_lablevel_old (id, level_number, description, lab_id)
            SELECT id, level_number, description, CAST(lab_id AS varchar)
            FROM interface_lablevel;
            
            -- Удаляем новую таблицу с CASCADE
            DROP TABLE interface_lablevel CASCADE;
            
            -- Переименовываем старую таблицу
            ALTER TABLE interface_lablevel_old RENAME TO interface_lablevel;
            
            -- Восстанавливаем последовательность
            SELECT setval(pg_get_serial_sequence('interface_lablevel', 'id'), 
                         (SELECT MAX(id) FROM interface_lablevel));
            """,
            'answers': """
            -- Создаем старую таблицу
            CREATE TABLE interface_answers_old (
                id SERIAL PRIMARY KEY,
                datetime timestamp,
                user_id bigint,
                lab_id varchar(255) NOT NULL,
                lab_task_id bigint,
                team_id bigint
            );
            
            -- Копируем данные обратно
            INSERT INTO interface_answers_old (id, datetime, user_id, lab_id, lab_task_id, team_id)
            SELECT id, datetime, user_id, CAST(lab_id AS varchar), lab_task_id, team_id
            FROM interface_answers;
            
            -- Удаляем новую таблицу с CASCADE
            DROP TABLE interface_answers CASCADE;
            
            -- Переименовываем старую таблицу
            ALTER TABLE interface_answers_old RENAME TO interface_answers;
            
            -- Восстанавливаем последовательность
            SELECT setval(pg_get_serial_sequence('interface_answers', 'id'), 
                         (SELECT MAX(id) FROM interface_answers));
            """,
            'kkzlab': """
            -- Создаем старую таблицу
            CREATE TABLE interface_kkzlab_old (
                id SERIAL PRIMARY KEY,
                num_tasks integer NOT NULL,
                kkz_id bigint NOT NULL,
                lab_id varchar(255) NOT NULL
            );
            
            -- Копируем данные обратно
            INSERT INTO interface_kkzlab_old (id, num_tasks, kkz_id, lab_id)
            SELECT id, num_tasks, kkz_id, CAST(lab_id AS varchar)
            FROM interface_kkzlab;
            
            -- Удаляем новую таблицу с CASCADE
            DROP TABLE interface_kkzlab CASCADE;
            
            -- Переименовываем старую таблицу
            ALTER TABLE interface_kkzlab_old RENAME TO interface_kkzlab;
            
            -- Восстанавливаем последовательность
            SELECT setval(pg_get_serial_sequence('interface_kkzlab', 'id'), 
                         (SELECT MAX(id) FROM interface_kkzlab));
            """,
            'competition': """
            -- Создаем старую таблицу
            CREATE TABLE interface_competition_old (
                id SERIAL PRIMARY KEY,
                slug varchar(255) NOT NULL,
                start timestamp NOT NULL,
                finish timestamp NOT NULL,
                participants INTEGER,
                lab_id varchar(255),
                level_id bigint,
                deleted boolean NOT NULL,
                kkz_id bigint,
                num_tasks integer NOT NULL
            );
            
            -- Копируем данные обратно
            INSERT INTO interface_competition_old (id, slug, start, finish, participants, lab_id, level_id, deleted, kkz_id, num_tasks)
            SELECT id, slug, start, finish, participants, CAST(lab_id AS varchar), level_id, deleted, kkz_id, num_tasks
            FROM interface_competition;
            
            -- Удаляем новую таблицу с CASCADE
            DROP TABLE interface_competition CASCADE;
            
            -- Переименовываем старую таблицу
            ALTER TABLE interface_competition_old RENAME TO interface_competition;
            
            -- Восстанавливаем последовательность
            SELECT setval(pg_get_serial_sequence('interface_competition', 'id'), 
                         (SELECT MAX(id) FROM interface_competition));
            """
        }
    
    return reverse_sql_templates.get(table_name, "")


class Migration(migrations.Migration):

    dependencies = [
        ('interface', '0030_fix_labtask_lab_id_type'),
    ]

    operations = [
        # Fix LabLevel.lab_id
        migrations.RunSQL(
            sql=get_sql_for_table('lablevel'),
            reverse_sql=get_reverse_sql_for_table('lablevel')
        ),
        
        # Fix Answers.lab_id
        migrations.RunSQL(
            sql=get_sql_for_table('answers'),
            reverse_sql=get_reverse_sql_for_table('answers')
        ),
        
        # Fix KkzLab.lab_id
        migrations.RunSQL(
            sql=get_sql_for_table('kkzlab'),
            reverse_sql=get_reverse_sql_for_table('kkzlab')
        ),
        
        # Fix Competition.lab_id
        migrations.RunSQL(
            sql=get_sql_for_table('competition'),
            reverse_sql=get_reverse_sql_for_table('competition')
        ),
    ] 