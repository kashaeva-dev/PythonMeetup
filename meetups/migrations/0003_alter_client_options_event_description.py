# Generated by Django 4.2.2 on 2023-06-21 13:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('meetups', '0002_rename_name_client_first_name_and_more'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='client',
            options={'verbose_name': 'Пользователь', 'verbose_name_plural': 'Пользователи'},
        ),
        migrations.AddField(
            model_name='event',
            name='description',
            field=models.TextField(blank=True, null=True, verbose_name='Описание мероприятия'),
        ),
    ]
