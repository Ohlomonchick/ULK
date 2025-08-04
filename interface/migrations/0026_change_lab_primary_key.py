# Generated manually for changing Lab primary key

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('interface', '0025_auto_20250731_2243'),
    ]

    operations = [
        # Шаг 1: Добавляем новое поле id как автоинкрементное
        migrations.AddField(
            model_name='lab',
            name='id',
            field=models.AutoField(primary_key=True, serialize=False, verbose_name='ID'),
        ),
        
        # Шаг 2: Убираем primary_key с поля name и делаем его unique
        migrations.AlterField(
            model_name='lab',
            name='name',
            field=models.CharField('Имя', max_length=255, unique=True),
        ),
    ] 