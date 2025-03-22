from django.db import migrations

def add_constitution_cards(apps, schema_editor):
    Card = apps.get_model('spinwheel', 'Card')
    
    cards_data = [
        # Common Cards
        {'title': 'Right to Equality', 'article_number': 'Article 14', 'content': 'Equality before law and equal protection of laws', 'rarity': 'COMMON'},
        {'title': 'Right to Freedom', 'article_number': 'Article 19', 'content': 'Protection of 6 rights regarding freedom of speech, assembly, etc.', 'rarity': 'COMMON'},
        {'title': 'Right to Education', 'article_number': 'Article 21A', 'content': 'Free and compulsory education for children', 'rarity': 'COMMON'},
        
        # Rare Cards
        {'title': 'Fundamental Rights', 'article_number': 'Article 12-35', 'content': 'Basic human rights guaranteed to all citizens', 'rarity': 'RARE'},
        {'title': 'Directive Principles', 'article_number': 'Article 36-51', 'content': 'Guidelines for state policy making', 'rarity': 'RARE'},
        {'title': 'Right to Privacy', 'article_number': 'Article 21', 'content': 'Fundamental right to privacy', 'rarity': 'RARE'},
        
        # Epic Cards
        {'title': 'Preamble', 'article_number': 'Preamble', 'content': 'Introduction to the Constitution of India', 'rarity': 'EPIC'},
        {'title': 'Emergency Powers', 'article_number': 'Article 352', 'content': 'Powers during national emergency', 'rarity': 'EPIC'},
        {'title': 'Supreme Court', 'article_number': 'Article 124', 'content': 'Establishment and constitution of Supreme Court', 'rarity': 'EPIC'},
    ]
    
    for card_data in cards_data:
        Card.objects.create(**card_data)

def remove_constitution_cards(apps, schema_editor):
    Card = apps.get_model('spinwheel', 'Card')
    Card.objects.all().delete()

class Migration(migrations.Migration):
    dependencies = [
        ('spinwheel', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(add_constitution_cards, remove_constitution_cards),
    ] 