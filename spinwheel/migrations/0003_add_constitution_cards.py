from django.db import migrations

def add_constitution_cards(apps, schema_editor):
    Card = apps.get_model('spinwheel', 'Card')
    
    cards_data = [
        # Common Cards
        {
            'title': 'Right to Equality',
            'article_number': 'Article 14',
            'content': 'The State shall not deny to any person equality before the law or the equal protection of the laws within the territory of India.',
            'rarity': 'COMMON'
        },
        {
            'title': 'Freedom of Speech',
            'article_number': 'Article 19(1)(a)',
            'content': 'All citizens shall have the right to freedom of speech and expression.',
            'rarity': 'COMMON'
        },
        {
            'title': 'Right to Education',
            'article_number': 'Article 21A',
            'content': 'The State shall provide free and compulsory education to all children between age six and fourteen years.',
            'rarity': 'COMMON'
        },
        
        # Rare Cards
        {
            'title': 'Right to Life',
            'article_number': 'Article 21',
            'content': 'No person shall be deprived of his life or personal liberty except according to procedure established by law.',
            'rarity': 'RARE'
        },
        {
            'title': 'Freedom of Religion',
            'article_number': 'Article 25',
            'content': 'All persons are equally entitled to freedom of conscience and the right to freely profess, practice, and propagate religion.',
            'rarity': 'RARE'
        },
        {
            'title': 'Cultural Rights',
            'article_number': 'Article 29',
            'content': 'Any section of the citizens having a distinct language, script or culture of its own shall have the right to conserve the same.',
            'rarity': 'RARE'
        },
        
        # Epic Cards
        {
            'title': 'Constitutional Remedies',
            'article_number': 'Article 32',
            'content': 'The right to move the Supreme Court for the enforcement of fundamental rights is guaranteed.',
            'rarity': 'EPIC'
        },
        {
            'title': 'Federal Structure',
            'article_number': 'Article 1',
            'content': 'India, that is Bharat, shall be a Union of States.',
            'rarity': 'EPIC'
        },
        {
            'title': 'Fundamental Duties',
            'article_number': 'Article 51A',
            'content': 'It shall be the duty of every citizen of India to abide by the Constitution and respect its ideals and institutions.',
            'rarity': 'EPIC'
        },
    ]
    
    for card_data in cards_data:
        Card.objects.create(**card_data)

def remove_constitution_cards(apps, schema_editor):
    Card = apps.get_model('spinwheel', 'Card')
    Card.objects.all().delete()

class Migration(migrations.Migration):
    dependencies = [
        ('spinwheel', '0002_add_constitution_cards'),  # Update this to your previous migration
    ]

    operations = [
        migrations.RunPython(add_constitution_cards, remove_constitution_cards),
    ] 