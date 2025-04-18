import random
import os
import requests
from django.core.management.base import BaseCommand
from django.utils.text import Truncator
from django.conf import settings
from dynamicDB.models import SubTopic
from spinwheel.models import Card, CardCombo

class Command(BaseCommand):
    help = 'Generate spinwheel cards using dynamicDB data enhanced by Gemini'

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
            CardCombo.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('Successfully cleared all existing cards and combos'))

        # Get API key from settings or environment
        api_key = getattr(settings, 'GEMINI_API_KEY', os.environ.get('GEMINI_API_KEY'))
        
        if not api_key:
            self.stdout.write(self.style.ERROR(
                'No Gemini API key found. Set GEMINI_API_KEY in settings or environment variables.'
            ))
            return
            
        # Get all SubTopics from dynamicDB
        subtopics = SubTopic.objects.all().select_related('topic_group')
        
        if not subtopics.exists():
            self.stdout.write(self.style.ERROR('No SubTopics found in dynamicDB. Please create content first.'))
            return
            
        self.stdout.write(f'Found {subtopics.count()} SubTopics in dynamicDB. Generating enhanced card content with Gemini...')
        
        # Generate cards from subtopics
        cards_created = self._generate_enhanced_cards(subtopics, api_key)
        
        # Create card combos
        self._generate_card_combos()
        
        self.stdout.write(self.style.SUCCESS(f'Successfully created {cards_created} cards with Gemini-enhanced content'))

    def _generate_enhanced_cards(self, subtopics, api_key):
        """Generate cards with Gemini-enhanced content from SubTopics"""
        cards_created = 0
        
        for subtopic in subtopics:
            # Create article number from topic group and subtopic IDs
            article_number = f"C{subtopic.topic_group.id}-{subtopic.id}"
            
            # Get enhanced content from Gemini using the topic title and existing description
            if subtopic.summary:
                base_content = subtopic.summary
            else:
                base_content = subtopic.description or f"Topic about {subtopic.title}"
            
            try:
                # Generate enhanced content with Gemini
                enhanced_content = self._get_gemini_enhancement(api_key, subtopic.title, base_content)
                
                if not enhanced_content:
                    self.stdout.write(self.style.WARNING(f"Failed to enhance content for '{subtopic.title}'. Using original content."))
                    enhanced_content = base_content
                    
                # Create cards with different rarities and content lengths
                rarities = ['COMMON', 'RARE', 'EPIC']
                
                for rarity in rarities:
                    # Adjust content length based on rarity
                    if rarity == 'COMMON':
                        max_length = 100
                        truncated_content = Truncator(enhanced_content).chars(max_length)
                        base_price = random.randint(50, 150)
                    elif rarity == 'RARE':
                        max_length = 200
                        truncated_content = Truncator(enhanced_content).chars(max_length)
                        base_price = random.randint(200, 400)
                    else:  # EPIC
                        truncated_content = enhanced_content
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
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error generating card for {subtopic.title}: {e}"))
                
        return cards_created

    def _get_gemini_enhancement(self, api_key, title, existing_content):
        """Use Gemini API to enhance the existing content"""
        prompt = f"""
        I have the following information about "{title}" from the Indian Constitution:
        
        "{existing_content}"
        
        Please enhance and improve this content to create a concise, educational card description 
        (150-200 words) about this topic. Focus on factual information, key principles, and significance.
        Keep the same overall meaning but make it more engaging and informative.
        Write in a clear, neutral tone suitable for educational content.
        Do not include any statements about being AI or providing information. Just write the content.
        """
        
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.0-pro:generateContent"
        headers = {"Content-Type": "application/json"}
        params = {"key": api_key}
        
        data = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 800,
                "topP": 0.95
            }
        }
        
        try:
            response = requests.post(url, headers=headers, params=params, json=data, timeout=30)
            
            if response.status_code == 200:
                response_data = response.json()
                
                if 'candidates' in response_data and response_data['candidates']:
                    first_candidate = response_data['candidates'][0]
                    if 'content' in first_candidate and 'parts' in first_candidate['content']:
                        parts = first_candidate['content']['parts']
                        if parts and 'text' in parts[0]:
                            return parts[0]['text'].strip()
            
            self.stdout.write(self.style.WARNING(
                f"API call failed, status: {response.status_code}, "
                f"response: {response.text[:100]}..."
            ))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error calling Gemini API: {e}"))
        
        return None

    def _generate_card_combos(self):
        """Generate card combos based on existing cards"""
        # Define thematic categories for grouping cards
        thematic_groups = {
            'Rights': ['Right', 'Freedom', 'Equality', 'Fundamental', 'Liberty'],
            'Structure': ['Federal', 'Parliamentary', 'President', 'Amendment', 'Structure'],
            'Governance': ['Directive', 'Executive', 'Parliament', 'Governance', 'Policy'],
            'Civic': ['Duty', 'Citizen', 'Election', 'Vote', 'Civic'],
            'Philosophy': ['Preamble', 'Secularism', 'Socialist', 'Democratic', 'Republic']
        }
        
        # Get all unique cards (ignoring rarity)
        cards = Card.objects.values('article_number', 'title').distinct()
        
        combos_created = 0
        
        # Create a combo for each thematic group where possible
        for theme_name, keywords in thematic_groups.items():
            # Find cards that match this theme
            matching_cards = []
            
            for card in cards:
                # Check if any keyword appears in title
                if any(keyword.lower() in card['title'].lower() for keyword in keywords):
                    # Get one rarity variant of this card (preferably EPIC)
                    card_obj = Card.objects.filter(
                        article_number=card['article_number'],
                        rarity='EPIC'
                    ).first() or Card.objects.filter(
                        article_number=card['article_number']
                    ).first()
                    
                    if card_obj:
                        matching_cards.append(card_obj)
            
            # Create combo if we have at least 3 matching cards
            if len(matching_cards) >= 3:
                # Select 3-5 cards for the combo
                selected_cards = matching_cards[:min(5, len(matching_cards))]
                
                # Create the combo
                combo, created = CardCombo.objects.get_or_create(
                    name=f"{theme_name} Collection",
                    defaults={
                        'description': f"A collection of cards related to {theme_name.lower()} aspects of the Constitution.",
                        'bonus_coins': random.randint(300, 1000)
                    }
                )
                
                # Add the cards to the combo
                combo.required_cards.set(selected_cards)
                
                action = 'Created' if created else 'Updated'
                combos_created += 1 if created else 0
                
                self.stdout.write(f"{action} combo: {combo.name} with {combo.required_cards.count()} cards")
                
        self.stdout.write(self.style.SUCCESS(f'Successfully created {combos_created} card combos')) 