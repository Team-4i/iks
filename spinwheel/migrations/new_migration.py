from django.db import migrations, models
import django.utils.timezone

class Migration(migrations.Migration):

    dependencies = [
        ('spinwheel', '0007_spinresult'),  # Update this to your last migration
    ]

    operations = [
        migrations.AddField(
            model_name='playerprofile',
            name='last_spin_refill',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
    ] 