import random
import os
import json
import requests
from django.core.management.base import BaseCommand
from django.utils.text import Truncator
from django.db.models import Count
from django.conf import settings
from dynamicDB.models import MainTopic, SubTopic
from spinwheel.models import Card, CardCombo

class Command(BaseCommand):
    help = 'Prepare spinwheel data from dynamicDB or sample data if none exists'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing cards before generating new ones',
        )
        parser.add_argument(
            '--force-sample',
            action='store_true',
            help='Force using sample data even if dynamicDB data exists',
        )
        parser.add_argument(
            '--sample-count',
            type=int,
            default=10,
            help='Number of sample articles to generate if using sample data',
        )
        parser.add_argument(
            '--use-gemini',
            action='store_true',
            help='Use Google Gemini API to generate content',
        )
        parser.add_argument(
            '--topics',
            type=str,
            help='Comma-separated list of topics to generate content for (with --use-gemini)',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write('Clearing existing cards...')
            Card.objects.all().delete()
            CardCombo.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('Successfully cleared all existing cards and combos'))

        # Check if we should use dynamicDB data, sample data, or Gemini
        use_sample_data = options['force_sample']
        use_gemini = options['use_gemini']
        
        if use_gemini:
            self.stdout.write('Using Google Gemini to generate card content...')
            cards_created = self._generate_with_gemini(options.get('topics'))
        elif not use_sample_data:
            # Count subtopics to see if there's enough dynamicDB data
            subtopic_count = SubTopic.objects.count()
            if subtopic_count < 5:  # Arbitrary threshold
                self.stdout.write(self.style.WARNING(f'Only {subtopic_count} SubTopics found in dynamicDB. Using sample data instead.'))
                use_sample_data = True
            else:
                self.stdout.write(f'Found {subtopic_count} SubTopics in dynamicDB. Using real data.')
                cards_created = self._generate_from_dynamicdb()
        
        if use_sample_data and not use_gemini:
            cards_created = self._generate_sample_data(options['sample_count'])
            
        # Create some card combos based on available cards
        self._generate_card_combos()
        
        self.stdout.write(self.style.SUCCESS(f'Successfully created {cards_created} new cards and associated combos'))

    def _generate_with_gemini(self, topics_input):
        """Generate card content using Google Gemini API"""
        # Default topics if none provided
        default_topics = [
            "Fundamental Rights", "Directive Principles", "Right to Equality",
            "Right to Freedom", "Federal Structure", "Parliamentary System",
            "Judicial Review", "Fundamental Duties", "Emergency Provisions",
            "Amendment Process", "Citizenship", "President of India",
            "Secularism", "Preamble", "Elections"
        ]
        
        # Parse topics from input or use defaults
        if topics_input:
            topics = [t.strip() for t in topics_input.split(',')]
        else:
            topics = default_topics[:10]  # Limit to 10 topics by default to avoid API quota issues
        
        self.stdout.write(f"Generating content for {len(topics)} topics...")
        
        cards_created = 0
        
        # Try to get API key from settings or environment
        api_key = getattr(settings, 'GEMINI_API_KEY', os.environ.get('GEMINI_API_KEY'))
        
        if not api_key:
            self.stdout.write(self.style.WARNING(
                'No Gemini API key found. Set GEMINI_API_KEY in settings or environment variables. '
                'Falling back to sample data.'
            ))
            return self._generate_sample_data(len(topics))
        
        # Process each topic
        for i, topic in enumerate(topics):
            try:
                content = self._get_gemini_content(api_key, topic)
                
                if not content:
                    self.stdout.write(self.style.WARNING(f"Failed to get content for {topic}. Using fallback content."))
                    content = f"Information about {topic} in the Indian Constitution. This is fallback content."
                
                # Create cards with different rarities
                article_number = f"G{i+1}"
                rarities = ['COMMON', 'RARE', 'EPIC']
                
                for rarity in rarities:
                    # Adjust content length based on rarity
                    if rarity == 'COMMON':
                        max_length = 100
                        truncated_content = Truncator(content).chars(max_length)
                        base_price = random.randint(50, 150)
                    elif rarity == 'RARE':
                        max_length = 200
                        truncated_content = Truncator(content).chars(max_length)
                        base_price = random.randint(200, 400)
                    else:  # EPIC
                        truncated_content = content
                        base_price = random.randint(500, 1000)
                    
                    # Create the card
                    card, created = Card.objects.update_or_create(
                        article_number=article_number,
                        rarity=rarity,
                        defaults={
                            'title': topic,
                            'content': truncated_content,
                            'base_price': base_price
                        }
                    )
                    
                    action = 'Created' if created else 'Updated'
                    cards_created += 1 if created else 0
                    
                    self.stdout.write(f"{action} card: {card.title} ({rarity})")
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error generating content for {topic}: {e}"))
        
        return cards_created

    def _get_gemini_content(self, api_key, topic, max_retries=2):
        """Get content from Gemini API for a specific constitutional topic"""
        prompt = f"""
        Generate a concise, educational description (150-200 words) about "{topic}" as it relates to the Indian Constitution.
        Focus on factual information, key principles, and significance. 
        Maintain a neutral, informative tone suitable for educational content.
        Do not include any disclaimers or statements about being an AI. Just provide the content.
        """
        
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.0-pro:generateContent"
        headers = {
            "Content-Type": "application/json",
        }
        
        params = {
            "key": api_key
        }
        
        data = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 800,
                "topP": 0.95
            }
        }
        
        for attempt in range(max_retries):
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
                    f"API call attempt {attempt + 1} failed, status: {response.status_code}, "
                    f"response: {response.text[:100]}..."
                ))
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error on API call attempt {attempt + 1}: {e}"))
        
        return None

    def _generate_from_dynamicdb(self):
        """Generate cards from dynamicDB SubTopics"""
        subtopics = SubTopic.objects.all().select_related('topic_group')
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
                # Adjust content length based on rarity
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
                
        return cards_created

    def _generate_sample_data(self, count):
        """Generate sample card data for prototyping"""
        # Sample constitutional articles and topics
        constitutional_samples = [
            {
                "title": "Fundamental Rights",
                "content": "The fundamental rights section of the Constitution guarantees citizens basic human rights regardless of race, place of birth, religion, caste, gender, or other factors. These include right to equality, freedom, against exploitation, freedom of religion, cultural and educational rights, and right to constitutional remedies."
            },
            {
                "title": "Directive Principles",
                "content": "The Directive Principles of State Policy in the Constitution provide guidelines for the government to ensure social and economic democracy. These include principles of equal justice, ownership distribution, protection of workers and children, uniform civil code, and environmental protection."
            },
            {
                "title": "Right to Equality",
                "content": "Articles 14-18 guarantee equality before law, prohibition of discrimination, equality of opportunity in public employment, abolition of untouchability, and abolition of titles except military or academic distinctions."
            },
            {
                "title": "Right to Freedom",
                "content": "Articles 19-22 protect basic freedoms like speech and expression, assembly, association, movement, residence, and practicing any profession. Restrictions are permitted only on grounds of sovereignty, security, public order, decency, or morality."
            },
            {
                "title": "Federal Structure",
                "content": "The Constitution establishes a federal structure with division of powers between the Union and the States. The legislative powers are divided through Union List, State List, and Concurrent List."
            },
            {
                "title": "Parliamentary System",
                "content": "The Constitution establishes a parliamentary form of government at both the Union and State levels. The executive is responsible to the legislature for all its policies and actions."
            },
            {
                "title": "Judicial Review",
                "content": "The Constitution grants the judiciary the power of judicial review to examine the constitutionality of legislative enactments and executive orders. This ensures checks and balances against arbitrary actions."
            },
            {
                "title": "Fundamental Duties",
                "content": "Added by the 42nd Amendment in 1976, Fundamental Duties in Article 51A prescribe moral obligations of citizens to promote patriotism, protect environment, develop scientific temper, and strive towards excellence."
            },
            {
                "title": "Emergency Provisions",
                "content": "Articles 352-360 provide for three types of emergencies: National, State, and Financial. During emergencies, fundamental rights may be suspended and the federal structure may transform into a unitary one."
            },
            {
                "title": "Amendment Process",
                "content": "Article 368 deals with the amendment procedure of the Constitution. Some provisions require special majority, while others need ratification by State legislatures, showing the flexible yet rigid nature of the Constitution."
            },
            {
                "title": "Citizenship",
                "content": "Articles 5-11 define citizenship by birth, descent, registration, naturalization, and incorporation of territory. The Constitution initially provided for single citizenship, unlike dual citizenship in some federal systems."
            },
            {
                "title": "President of India",
                "content": "Articles 52-62 establish the President as the head of state elected indirectly by an electoral college. Though executive power is vested in the President, actual functions are performed by the Council of Ministers headed by the Prime Minister."
            },
            {
                "title": "Secularism",
                "content": "The Constitution establishes India as a secular state, guaranteeing freedom of conscience and free profession, practice, and propagation of religion. The state treats all religions equally and does not discriminate on religious grounds."
            },
            {
                "title": "Preamble",
                "content": "The Preamble declares India as a sovereign, socialist, secular, democratic republic, securing justice, liberty, equality, and fraternity for all citizens. It embodies the basic philosophy and fundamental values of the Constitution."
            },
            {
                "title": "Elections",
                "content": "Articles 324-329 establish an independent Election Commission to conduct free and fair elections. Universal adult suffrage is granted to all citizens above 18 years, irrespective of race, religion, caste, gender, or other factors."
            }
        ]
        
        # Create sample cards with different rarities
        rarities = ['COMMON', 'RARE', 'EPIC']
        cards_created = 0
        
        for i, sample in enumerate(constitutional_samples[:count]):
            article_number = f"A{i+1}"
            
            for rarity in rarities:
                # Adjust content length based on rarity
                if rarity == 'COMMON':
                    max_length = 100
                    content = sample["content"][:max_length] + "..."
                    base_price = random.randint(50, 150)
                elif rarity == 'RARE':
                    max_length = 200
                    content = sample["content"][:max_length] + "..." if len(sample["content"]) > max_length else sample["content"]
                    base_price = random.randint(200, 400)
                else:  # EPIC
                    content = sample["content"]
                    base_price = random.randint(500, 1000)
                
                # Create the card
                card, created = Card.objects.update_or_create(
                    article_number=article_number,
                    rarity=rarity,
                    defaults={
                        'title': sample["title"],
                        'content': content,
                        'base_price': base_price
                    }
                )
                
                action = 'Created' if created else 'Updated'
                cards_created += 1 if created else 0
                
                self.stdout.write(f"{action} card: {card.title} ({rarity})")
                
        return cards_created
    
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
                self.stdout.write(f"{action} combo: {combo.name} with {combo.required_cards.count()} cards") 