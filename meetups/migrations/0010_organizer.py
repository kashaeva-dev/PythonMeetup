# Generated by Django 4.2.2 on 2023-06-25 16:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('meetups', '0009_alter_question_question_number_donate'),
    ]

    operations = [
        migrations.CreateModel(
            name='Organizer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('user_id', models.CharField(max_length=20, verbose_name='ID организатора')),
                ('first_name', models.CharField(blank=True, max_length=40, null=True, verbose_name='Имя организатора')),
                ('last_name', models.CharField(blank=True, max_length=100, null=True, verbose_name='Фамилия организатора')),
                ('events', models.ManyToManyField(related_name='organizer', to='meetups.event', verbose_name='Мероприятие')),
            ],
            options={
                'verbose_name': 'Организатор',
                'verbose_name_plural': 'Организаторы',
            },
        ),
    ]
