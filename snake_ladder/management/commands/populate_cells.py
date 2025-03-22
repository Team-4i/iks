from django.core.management.base import BaseCommand
import random
import time
import google.generativeai as genai
from snake_ladder.models import Cell, CellContent
from dbs.models import ConstitutionalArticle
import json

class Command(BaseCommand):
    help = 'Populates cells with educational content from Constitutional Articles'

    GOOGLE_API_KEY = 'AIzaSyBIZIZoovhNdzrqzh4u71OOfFMiBRi52tk'

    def __init__(self):
        super().__init__()
        genai.configure(api_key=self.GOOGLE_API_KEY)
        self.model = genai.GenerativeModel('gemini-pro')

    def get_constitutional_data(self):
        """Fetch articles for Part 5 Judiciary"""
        articles = ConstitutionalArticle.objects.filter(
            part=5,
            type='LEG'
        ).values('article_number', 'article_title', 'simplified_explanation', 'original_text')
        
        if not articles:
            self.stdout.write(self.style.WARNING('No articles found for Part 5 JUD'))
            return "", []

        articles_text = "\n\n".join([
            f"Article {art['article_number']}: {art['article_title']}\n"
            f"Explanation: {art['simplified_explanation']}\n"
            f"Original: {art['original_text']}"
            for art in articles
        ])
        return articles_text, articles

    def generate_content_variations(self, articles_text):
        """Generate exactly 80 content variations for normal cells"""
        if not articles_text:
            return []

        prompt = f"""
        Based on these Constitutional Articles about Part 5 (Judiciary):

        {articles_text}

        Generate educational content in exactly this JSON format:
        {{
            "content": [
                {{
                    "content": "Did you know? [Insert interesting fact]",
                    "topic": "[Topic name]"
                }},
                {{
                    "content": "[Topic name]: [2-3 sentences explaining a concept]",
                    "topic": "[Topic name]"
                }}
            ]
        }}

        Rules:
        1. Generate exactly 80 items (for 80 normal cells)
        2. Alternate between "Did you know?" facts and concept explanations/explanations of articles
        3. Each content must be based on the provided articles
        4. Include article references where applicable
        5. Keep "Did you know?" facts concise (15-20 words)
        6. Make concept explanations 2-3 sentences long
        7. Ensure all content is unique
        8. Use proper JSON format with double quotes
        """

        try:
            response = self.model.generate_content(prompt)
            content_data = json.loads(response.text)
            return content_data.get('content', [])
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error generating content: {str(e)}'))
            return []

    def handle(self, *args, **options):


        self.stdout.write('Fetching Constitutional Articles for Part 5 LEG...')
        articles_text, articles = self.get_constitutional_data()
        
        if not articles:
            self.stdout.write(self.style.ERROR('No articles found. Aborting.'))
            return

        self.stdout.write('Generating content variations...')
        content_variations = self.generate_content_variations(articles_text)
        
        if not content_variations:
            self.stdout.write(self.style.ERROR('No content generated. Aborting.'))
            return

        if len(content_variations) < 80:
            self.stdout.write(self.style.ERROR(f'Not enough content generated. Need 80, got {len(content_variations)}'))
            return

        # Create all cells first (1-100)
        self.stdout.write('Creating all cells...')
        for number in range(1, 101):
            Cell.objects.create(number=number)

        # Create CellContent objects and map to normal cells
        self.stdout.write('Creating and mapping content...')
        normal_cell_count = 0
        content_index = 0

        for number in range(1, 101):
            cell = Cell.objects.get(number=number)
            
            if not Cell.is_snake_ladder_cell(number):
                # Create content for normal cell
                content_data = content_variations[content_index]
                cell_content = CellContent.objects.create(
                    content=content_data['content'],
                    topic=content_data['topic'],
                    part=5,  # Part 5
                    type='LEG'  # Judiciary
                )
                
                # Add to cell's contents and set as current
                cell.contents.add(cell_content)
                cell.current_content = cell_content
                cell.save()
                
                normal_cell_count += 1
                content_index += 1

        # Verify counts
        normal_cells = Cell.objects.filter(cell_type='NORMAL').count()
        snake_ladder_cells = Cell.objects.filter(cell_type='SNAKE_LADDER').count()
        content_count = CellContent.objects.count()

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully populated cells:\n'
                f'- Normal cells: {normal_cells} (should be 80)\n'
                f'- Snake/Ladder cells: {snake_ladder_cells} (should be 20)\n'
                f'- Content pieces created: {content_count} (should be 80)\n'
                f'All normal cells have Part 5 LEG content mapped.'
            )
        )