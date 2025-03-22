from django.db import migrations, models

def duplicate_cards_with_rarities(apps, schema_editor):
    Card = apps.get_model('spinwheel', 'Card')
    
    # Store existing cards
    existing_cards = list(Card.objects.all())
    
    # Clear existing cards
    Card.objects.all().delete()
    
    # Recreate cards with different rarities
    for card in existing_cards:
        base_price = {
            'Article 14': 100,
            'Article 19': 100,
            'Article 21A': 100,
            'Article 21': 150,
            'Article 32': 200,
            # Add more base prices as needed
        }.get(card.article_number, 100)
        
        # Create three versions of each card
        Card.objects.create(
            title=card.title,
            article_number=card.article_number,
            content=card.content,
            rarity='COMMON',
            base_price=base_price
        )
        Card.objects.create(
            title=f"{card.title} (Rare)",
            article_number=card.article_number,
            content=card.content,
            rarity='RARE',
            base_price=base_price
        )
        Card.objects.create(
            title=f"{card.title} (Epic)",
            article_number=card.article_number,
            content=card.content,
            rarity='EPIC',
            base_price=base_price
        )

def reverse_migration(apps, schema_editor):
    Card = apps.get_model('spinwheel', 'Card')
    Card.objects.all().delete()

class Migration(migrations.Migration):
    dependencies = [
        ('spinwheel', '0007_spinresult'),  # Updated to use your last migration
    ]

    operations = [
        migrations.AddField(
            model_name='card',
            name='base_price',
            field=models.IntegerField(default=100),
        ),
        migrations.AlterUniqueTogether(
            name='card',
            unique_together={('article_number', 'rarity')},
        ),
        migrations.RunPython(duplicate_cards_with_rarities, reverse_migration),
    ] 