# Generated manually to fix Lab.id field
from django.db import migrations, models


def ensure_primary_key_exists(apps, schema_editor):
    """Убеждается, что у таблицы interface_lab есть первичный ключ."""
    vendor = schema_editor.connection.vendor
    db_table = 'interface_lab'
    quoted_table = schema_editor.connection.ops.quote_name(db_table)
    
    with schema_editor.connection.cursor() as cursor:
        if vendor == 'postgresql':
            # Проверяем, есть ли уже первичный ключ
            cursor.execute("""
                SELECT constraint_name 
                FROM information_schema.table_constraints 
                WHERE table_name = %s 
                AND constraint_type = 'PRIMARY KEY'
            """, [db_table])
            
            if not cursor.fetchone():
                # Первичного ключа нет, добавляем его
                cursor.execute(f"""
                    ALTER TABLE {quoted_table} 
                    ADD CONSTRAINT interface_lab_pkey PRIMARY KEY (id)
                """)
        elif vendor == 'sqlite':
            # В SQLite проверяем через PRAGMA
            cursor.execute(f"PRAGMA table_info([{db_table}])")
            columns = cursor.fetchall()
            has_pk = any(col[5] == 1 for col in columns if col[1] == 'id')
            
            if not has_pk:
                # Создаем уникальный индекс как замену первичного ключа
                cursor.execute(f"""
                    CREATE UNIQUE INDEX IF NOT EXISTS interface_lab_pkey 
                    ON {quoted_table}(id)
                """)


def remove_primary_key_if_added(apps, schema_editor):
    """Удаляет первичный ключ, если он был добавлен этой миграцией."""
    vendor = schema_editor.connection.vendor
    db_table = 'interface_lab'
    quoted_table = schema_editor.connection.ops.quote_name(db_table)
    
    with schema_editor.connection.cursor() as cursor:
        if vendor == 'postgresql':
            try:
                cursor.execute(f"""
                    ALTER TABLE {quoted_table} 
                    DROP CONSTRAINT IF EXISTS interface_lab_pkey
                """)
            except Exception:
                pass
        elif vendor == 'sqlite':
            try:
                cursor.execute(f"DROP INDEX IF EXISTS interface_lab_pkey")
            except Exception:
                pass


class Migration(migrations.Migration):
    dependencies = [
        ('interface', '0045_merge_20250905_2321'),
    ]

    operations = [
        migrations.RunPython(
            ensure_primary_key_exists,
            remove_primary_key_if_added,
        ),
        migrations.AlterField(
            model_name='lab',
            name='id',
            field=models.AutoField(primary_key=True),
        ),
    ]
