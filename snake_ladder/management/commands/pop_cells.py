from django.core.management.base import BaseCommand
import random
import time
import json
import re
import traceback
import os
import logging

# Ensure you have these imports in your project
import google.generativeai as genai
from snake_ladder.models import Cell, CellContent
from dbs.models import ConstitutionalArticle

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Populates cells with educational content from Constitutional Articles'

    def __init__(self):
        super().__init__()
        # List of API keys to rotate through
        self.api_keys = [
            'AIzaSyBIZIZoovhNdzrqzh4u71OOfFMiBRi52tk',
            'AIzaSyC2Ac0vxf3jnqr6gM8NKMHSeTCPzp3qXag',
            'AIzaSyAk3aabAsfIkyNKWf6zAWbIQLYFfwmjZ6M',
            'AIzaSyB-4D_fwclYePdnf8hyLlPKlqHqy15CZts',
            "AIzaSyBIZIZoovhNdzrqzh4u71OOfFMiBRi52tk",
            "AIzaSyA72KTukqeX6NklIoZiWJZqjXFMceAS6NM",
            "AIzaSyC2Ac0vxf3jnqr6gM8NKMHSeTCPzp3qXag",
            'AIzaSyCXvFUsqrWVuXgCDBNHXd7NKS_c-IH0NGI',
            





            # Add more API keys as needed
        ]
        self.current_key_index = 0
        self.last_request_time = 0
        self.min_request_interval = 1  # Minimum seconds between requests
        
        self.initialize_api()

    def initialize_api(self):
        """Initialize the API with the current key"""
        if not self.api_keys:
            self.stdout.write(self.style.ERROR('No API keys available'))
            return False
        
        genai.configure(api_key=self.api_keys[self.current_key_index])
        self.model = genai.GenerativeModel('gemini-pro')
        return True

    def rotate_api_key(self):
        """Rotate to the next available API key"""
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        self.stdout.write(self.style.WARNING(f'Rotating to API key {self.current_key_index + 1}'))
        return self.initialize_api()

    def make_api_request(self, prompt, max_retries=3):
        """Make API request with rate limiting and key rotation"""
        for attempt in range(max_retries * len(self.api_keys)):
            # Enforce rate limiting
            current_time = time.time()
            time_since_last_request = current_time - self.last_request_time
            if time_since_last_request < self.min_request_interval:
                time.sleep(self.min_request_interval - time_since_last_request)

            try:
                generation_config = {
                    'temperature': 0.7,
                    'max_output_tokens': 2048,
                }
                
                response = self.model.generate_content(
                    prompt, 
                    generation_config=generation_config
                )
                self.last_request_time = time.time()
                return response

            except Exception as e:
                if '429' in str(e):  # Rate limit or quota exceeded
                    self.stdout.write(self.style.WARNING(f'API key {self.current_key_index + 1} exhausted'))
                    if not self.rotate_api_key():
                        self.stdout.write(self.style.ERROR('No more API keys available'))
                        raise
                    time.sleep(2)  # Wait before trying new key
                else:
                    raise

        raise Exception("All API keys exhausted and max retries reached")

    def get_constitutional_data(self):
        """Fetch articles for Part 6 Executive"""
        articles = ConstitutionalArticle.objects.filter(
            part=6,
            type='EXEC'
        ).values('article_number', 'article_title', 'simplified_explanation', 'original_text')
        
        if not articles:
            self.stdout.write(self.style.WARNING('No articles found for Part 6 EXEC'))
            return "", []

        articles_text = "\n\n".join([
            f"Article {art['article_number']}: {art['article_title']}\n"
            f"Explanation: {art['simplified_explanation']}\n"
            f"Original: {art['original_text']}"
            for art in articles
        ])
        return articles_text, articles

    def safe_json_extract(self, text):
        """More robust JSON extraction"""
        try:
            # Try direct JSON extraction first
            return json.loads(text)
        except json.JSONDecodeError:
            # More robust regex for JSON extraction
            try:
                # Use a more standard regex approach
                json_match = re.search(r'\{.*\}', text, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group(0))
            except Exception:
                pass
            
            return None

    def generate_content_batch(self, articles_text, batch_size=20, max_retries=3):
        """Generate a batch of content variations with retry mechanism"""
        prompt = f"""
        Based on these Constitutional Articles about Part 6 (Executive):

        {articles_text}

        Generate exactly {batch_size} educational content items in this precise JSON format:
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
        1. Generate exactly {batch_size} items
        2. Alternate between "Did you know?" facts and concept explanations/explanations of articles
        3. Each content must must be unique and should be based on the provided articles
        4. Include article references where applicable
        5. Keep "Did you know?" facts concise (15-20 words)
        6. Make concept explanations 2-3 sentences long
        7. Ensure all content is unique
        8. Use proper JSON format with double quotes
        
        


        """

        try:
            response = self.make_api_request(prompt, max_retries)
            content_data = self.safe_json_extract(response.text)
            
            if content_data and 'content' in content_data:
                return content_data['content'][:batch_size]
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Batch generation error: {str(e)}'))
        
        # Fallback content
        return [
            {"content": f"Basic Executive Fact #{i+1}", "topic": "EXECiciary Basics"}
            for i in range(batch_size)
        ]

    def generate_content_variations(self, articles_text):
        """Generate exactly 80 content variations for normal cells"""
        if not articles_text:
            return []

        all_content = []
        batch_size = 20  # Generate in smaller batches
        batches_needed = 4  # To get 80 items total

        self.stdout.write('Generating content in batches...')
        
        for i in range(batches_needed):
            self.stdout.write(f'Generating batch {i+1}/{batches_needed}...')
            
            # Add exponential backoff for rate limiting
            backoff_time = 2 ** i  # 2, 4, 8, 16 seconds
            time.sleep(backoff_time)
            
            batch_content = self.generate_content_batch(articles_text, batch_size)
            if batch_content:
                all_content.extend(batch_content)

        # Ensure exactly 80 items
        while len(all_content) < 80:
            all_content.append({
                "content": f"Basic EXECiciary Fact #{len(all_content)+1}",
                "topic": "EXECiciary Basics"
            })

        return all_content[:80]  # Ensure exactly 80 items

    def handle(self, *args, **options):
        try:
            # Verify API configuration
            if not hasattr(self, 'model'):
                self.stdout.write(self.style.ERROR('API not configured. Check your API key.'))
                return



            self.stdout.write('Fetching Constitutional Articles for Part 6 EXEC...')
            articles_text, articles = self.get_constitutional_data()
            
            if not articles:
                self.stdout.write(self.style.ERROR('No articles found. Aborting.'))
                return

            self.stdout.write('Generating content variations...')
            content_variations = self.generate_content_variations(articles_text)
            
            if not content_variations:
                self.stdout.write(self.style.ERROR('No content generated. Aborting.'))
                return

            # Create all cells first (1-100)
            self.stdout.write('Creating cells if needed...')
            for number in range(1, 101):
                Cell.objects.get_or_create(number=number)  # Use get_or_create instead of bulk_create

            # Create CellContent objects and map to normal cells
            self.stdout.write('Creating and mapping content...')
            cell_contents_to_create = []
            
            # Filter out snake and ladder cells
            normal_cells = Cell.objects.filter(
                number__in=range(1, 101)
            ).exclude(
                number__in=Cell.SNAKE_LADDER_CELLS
            )

            for cell, content_data in zip(normal_cells[:80], content_variations):
                cell_content = CellContent.objects.create(
                    content=content_data['content'],
                    topic=content_data['topic'],
                    part=6,
                    type='EXEC'
                )
                # Add to cell's contents and set as current
                cell.contents.add(cell_content)
                cell.current_content = cell_content
                cell.save()

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
                    f'All normal cells have Part 6 EXEC content mapped.'
                )
            )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Unexpected error: {str(e)}'))
            self.stdout.write(traceback.format_exc())