# Generated manually to fix Lab.id field
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('interface', '0045_merge_20250905_2321'),
    ]

    operations = [
        migrations.AlterField(
            model_name='lab',
            name='id',
            field=models.AutoField(primary_key=True),
        ),
    ]
