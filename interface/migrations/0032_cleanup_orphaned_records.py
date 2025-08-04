# Generated manually to cleanup orphaned records with lab_id=0

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('interface', '0031_fix_all_lab_foreign_keys'),
    ]

    operations = [
        # Remove orphaned many-to-many references first
        migrations.RunSQL(
            sql="""
            DELETE FROM interface_kkzlab_tasks WHERE labtask_id IN (SELECT id FROM interface_labtask WHERE lab_id = 0);
            DELETE FROM interface_competition_tasks WHERE labtask_id IN (SELECT id FROM interface_labtask WHERE lab_id = 0);
            DELETE FROM interface_issuedlabs_tasks WHERE labtask_id IN (SELECT id FROM interface_labtask WHERE lab_id = 0);
            DELETE FROM interface_competition2user_tasks WHERE labtask_id IN (SELECT id FROM interface_labtask WHERE lab_id = 0);
            DELETE FROM interface_teamcompetition2team_tasks WHERE labtask_id IN (SELECT id FROM interface_labtask WHERE lab_id = 0);
            """,
            reverse_sql="""
            -- Cannot restore deleted records, so this is a no-op
            """
        ),
        
        # Remove LabTask records with lab_id=0
        migrations.RunSQL(
            sql="""
            DELETE FROM interface_labtask WHERE lab_id = 0;
            """,
            reverse_sql="""
            -- Cannot restore deleted records, so this is a no-op
            """
        ),
        
        # Remove LabLevel records with lab_id=0
        migrations.RunSQL(
            sql="""
            DELETE FROM interface_lablevel WHERE lab_id = 0;
            """,
            reverse_sql="""
            -- Cannot restore deleted records, so this is a no-op
            """
        ),
        
        # Remove Answers records with lab_id=0
        migrations.RunSQL(
            sql="""
            DELETE FROM interface_answers WHERE lab_id = 0;
            """,
            reverse_sql="""
            -- Cannot restore deleted records, so this is a no-op
            """
        ),
        
        # Remove KkzLab records with lab_id=0
        migrations.RunSQL(
            sql="""
            DELETE FROM interface_kkzlab WHERE lab_id = 0;
            """,
            reverse_sql="""
            -- Cannot restore deleted records, so this is a no-op
            """
        ),
        
        # Remove Competition records with lab_id=0
        migrations.RunSQL(
            sql="""
            DELETE FROM interface_competition WHERE lab_id = 0;
            """,
            reverse_sql="""
            -- Cannot restore deleted records, so this is a no-op
            """
        ),
    ] 