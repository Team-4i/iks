from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('flip_card', '0005_delete_leveldocuments'),
        ('dynamicDB', '0002_alter_pdfdocument_converted_image_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='LevelDocuments',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('level', models.IntegerField()),
                ('documents', models.ManyToManyField(to='dynamicDB.Topic')),
            ],
        ),
    ] 