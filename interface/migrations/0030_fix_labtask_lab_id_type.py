# Generated manually to fix FOREIGN KEY constraint issue

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('interface', '0029_fix_labtask_foreign_key'),
    ]

    operations = [
        migrations.RunSQL(
            # SQL для изменения типа поля lab_id с varchar на INTEGER
            sql="""
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
            """,
            reverse_sql="""
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
        ),
    ] 