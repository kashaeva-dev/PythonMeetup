# Generated by Django 4.2.2 on 2023-06-23 12:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('meetups', '0007_remove_question_title'),
    ]

    operations = [
        migrations.AddField(
            model_name='question',
            name='question_number',
            field=models.IntegerField(blank=True, null=True, verbose_name='Номер вопроса'),
        ),
    ]