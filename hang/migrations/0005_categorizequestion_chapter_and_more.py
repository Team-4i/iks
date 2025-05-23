# Generated by Django 5.1.2 on 2025-04-18 21:33

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dynamicDB', '0001_initial'),
        ('hang', '0004_hangmangame_points_playerstats_best_points_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='categorizequestion',
            name='chapter',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_questions', to='dynamicDB.chapter'),
        ),
        migrations.AddField(
            model_name='categorizequestion',
            name='main_topic',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_questions', to='dynamicDB.maintopic'),
        ),
        migrations.AddField(
            model_name='categorizequestion',
            name='sub_topic',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_questions', to='dynamicDB.subtopic'),
        ),
        migrations.AddField(
            model_name='categorizequestion',
            name='topic',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_questions', to='dynamicDB.topic'),
        ),
        migrations.AddField(
            model_name='fillblankquestion',
            name='chapter',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_questions', to='dynamicDB.chapter'),
        ),
        migrations.AddField(
            model_name='fillblankquestion',
            name='main_topic',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_questions', to='dynamicDB.maintopic'),
        ),
        migrations.AddField(
            model_name='fillblankquestion',
            name='sub_topic',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_questions', to='dynamicDB.subtopic'),
        ),
        migrations.AddField(
            model_name='fillblankquestion',
            name='topic',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_questions', to='dynamicDB.topic'),
        ),
        migrations.AddField(
            model_name='matchpairsquestion',
            name='chapter',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_questions', to='dynamicDB.chapter'),
        ),
        migrations.AddField(
            model_name='matchpairsquestion',
            name='main_topic',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_questions', to='dynamicDB.maintopic'),
        ),
        migrations.AddField(
            model_name='matchpairsquestion',
            name='sub_topic',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_questions', to='dynamicDB.subtopic'),
        ),
        migrations.AddField(
            model_name='matchpairsquestion',
            name='topic',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_questions', to='dynamicDB.topic'),
        ),
        migrations.AddField(
            model_name='mcqquestion',
            name='chapter',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_questions', to='dynamicDB.chapter'),
        ),
        migrations.AddField(
            model_name='mcqquestion',
            name='main_topic',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_questions', to='dynamicDB.maintopic'),
        ),
        migrations.AddField(
            model_name='mcqquestion',
            name='sub_topic',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_questions', to='dynamicDB.subtopic'),
        ),
        migrations.AddField(
            model_name='mcqquestion',
            name='topic',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_questions', to='dynamicDB.topic'),
        ),
        migrations.AddField(
            model_name='oddoneoutquestion',
            name='chapter',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_questions', to='dynamicDB.chapter'),
        ),
        migrations.AddField(
            model_name='oddoneoutquestion',
            name='main_topic',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_questions', to='dynamicDB.maintopic'),
        ),
        migrations.AddField(
            model_name='oddoneoutquestion',
            name='sub_topic',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_questions', to='dynamicDB.subtopic'),
        ),
        migrations.AddField(
            model_name='oddoneoutquestion',
            name='topic',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_questions', to='dynamicDB.topic'),
        ),
        migrations.AddField(
            model_name='truefalsequestion',
            name='chapter',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_questions', to='dynamicDB.chapter'),
        ),
        migrations.AddField(
            model_name='truefalsequestion',
            name='main_topic',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_questions', to='dynamicDB.maintopic'),
        ),
        migrations.AddField(
            model_name='truefalsequestion',
            name='sub_topic',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_questions', to='dynamicDB.subtopic'),
        ),
        migrations.AddField(
            model_name='truefalsequestion',
            name='topic',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_questions', to='dynamicDB.topic'),
        ),
        migrations.AddField(
            model_name='wordunscramblequestion',
            name='chapter',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_questions', to='dynamicDB.chapter'),
        ),
        migrations.AddField(
            model_name='wordunscramblequestion',
            name='main_topic',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_questions', to='dynamicDB.maintopic'),
        ),
        migrations.AddField(
            model_name='wordunscramblequestion',
            name='sub_topic',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_questions', to='dynamicDB.subtopic'),
        ),
        migrations.AddField(
            model_name='wordunscramblequestion',
            name='topic',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_questions', to='dynamicDB.topic'),
        ),
    ]
