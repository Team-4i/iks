# Generated by Django 5.1.2 on 2025-04-18 19:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hang', '0003_questioncategory_oddoneoutquestion_mcqquestion_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='hangmangame',
            name='points',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='playerstats',
            name='best_points',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='playerstats',
            name='total_points',
            field=models.IntegerField(default=0),
        ),
    ]
