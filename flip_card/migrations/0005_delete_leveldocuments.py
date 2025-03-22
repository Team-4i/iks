from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('flip_card', '0004_leveldocuments'),
    ]

    operations = [
        migrations.DeleteModel(
            name='LevelDocuments',
        ),
    ] 