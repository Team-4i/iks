import random
from django.core.management.base import BaseCommand
from django.utils.text import Truncator
from dynamicDB.models import MainTopic, SubTopic
from spinwheel.models import Card

class Command(BaseCommand):
    help = 'Generate card data for spinwheel app based on dynamicDB content'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing cards before generating new ones',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write('Clearing existing cards...')
            Card.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('Successfully cleared all existing cards'))

        # Get all SubTopics
        subtopics = SubTopic.objects.all().select_related('topic_group')
        
        if not subtopics.exists():
            self.stdout.write(self.style.WARNING('No SubTopics found in dynamicDB. Please create content first.'))
            return
            
        cards_created = 0
        
        for subtopic in subtopics:
            # Create article number from topic group and subtopic IDs
            article_number = f"C{subtopic.topic_group.id}-{subtopic.id}"
            
            # Create condensed content from subtopic summary or description
            if subtopic.summary.strip():
                content_source = subtopic.summary
            else:
                content_source = subtopic.description
                
            # Create cards with different rarities and content lengths
            rarities = ['COMMON', 'RARE', 'EPIC']
            
            for rarity in rarities:
                # Adjust content length based on rarity (Epic cards have more content)
                if rarity == 'COMMON':
                    max_length = 100
                elif rarity == 'RARE':
                    max_length = 200
                else:  # EPIC
                    max_length = 300
                
                # Truncate content to specified length
                truncated_content = Truncator(content_source).chars(max_length)
                
                # Set base price based on rarity
                if rarity == 'COMMON':
                    base_price = random.randint(50, 150)
                elif rarity == 'RARE':
                    base_price = random.randint(200, 400)
                else:  # EPIC
                    base_price = random.randint(500, 1000)
                
                # Create or update the card
                card, created = Card.objects.update_or_create(
                    article_number=article_number,
                    rarity=rarity,
                    defaults={
                        'title': subtopic.title,
                        'content': truncated_content,
                        'base_price': base_price
                    }
                )
                
                action = 'Created' if created else 'Updated'
                cards_created += 1 if created else 0
                
                self.stdout.write(f"{action} card: {card.title} ({rarity})")
        
        self.stdout.write(self.style.SUCCESS(f'Successfully created {cards_created} new cards')) 