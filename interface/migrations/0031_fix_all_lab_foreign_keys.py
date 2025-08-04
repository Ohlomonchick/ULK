# Generated manually to fix all FOREIGN KEY constraints referencing Lab

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('interface', '0030_fix_labtask_lab_id_type'),
    ]

    operations = [
        # Fix LabLevel.lab_id
        migrations.RunSQL(
            sql="""
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
            reverse_sql="""
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
            """
        ),
        
        # Fix Answers.lab_id
        migrations.RunSQL(
            sql="""
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
            reverse_sql="""
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
            """
        ),
        
        # Fix KkzLab.lab_id
        migrations.RunSQL(
            sql="""
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
            reverse_sql="""
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
            """
        ),
        
        # Fix Competition.lab_id
        migrations.RunSQL(
            sql="""
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
            """,
            reverse_sql="""
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
        ),
    ] 