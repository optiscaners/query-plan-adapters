# Generated by Django 4.2.4 on 2023-09-01 12:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('testapp', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='resource',
            name='related',
            field=models.ManyToManyField(to='testapp.nestedresource'),
        ),
        migrations.AddField(
            model_name='user',
            name='related',
            field=models.ManyToManyField(to='testapp.nestedresource'),
        ),
    ]
