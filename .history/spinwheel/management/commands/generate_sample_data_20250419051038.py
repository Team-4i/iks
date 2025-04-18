import random
from django.core.management.base import BaseCommand
from spinwheel.models import Card

class Command(BaseCommand):
    help = 'Generate sample card data for spinwheel app for prototyping'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing cards before generating new ones',
        )
        parser.add_argument(
            '--count',
            type=int,
            default=10,
            help='Number of sample articles to generate (default: 10)',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write('Clearing existing cards...')
            Card.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('Successfully cleared all existing cards'))

        count = options['count']
        
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
        
        self.stdout.write(self.style.SUCCESS(f'Successfully created {cards_created} new cards')) 