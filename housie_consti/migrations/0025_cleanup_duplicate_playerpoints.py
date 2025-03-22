from django.db import migrations

def cleanup_duplicate_playerpoints(apps, schema_editor):
    PlayerPoints = apps.get_model('housie_consti', 'PlayerPoints')
    
    # Get all unique room-player combinations
    seen_combinations = set()
    duplicates_to_delete = []
    
    for pp in PlayerPoints.objects.all().order_by('-id'):
        combination = (pp.room_id, pp.player_id)
        if combination in seen_combinations:
            duplicates_to_delete.append(pp.id)
        else:
            seen_combinations.add(combination)
    
    # Delete duplicates
    PlayerPoints.objects.filter(id__in=duplicates_to_delete).delete()

class Migration(migrations.Migration):
    dependencies = [
        ('housie_consti', '0024_playerpoints'),  # Adjust this to your previous migration
    ]

    operations = [
        migrations.RunPython(cleanup_duplicate_playerpoints),
        migrations.AlterUniqueTogether(
            name='playerpoints',
            unique_together={('room', 'player')},
        ),
    ] 