from django.core.management.base import BaseCommand
import random
import time
import json
import re
import traceback
import logging

import google.generativeai as genai
from snake_ladder.models import Cell, CellContent
from dbs.models import ConstitutionalArticle

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Populates cells with educational content from Constitutional Articles'

    def __init__(self):
        super().__init__()
        api_key = "AIzaSyA72KTukqeX6NklIoZiWJZqjXFMceAS6NM"  # Replace with your secure API key
        if not api_key:
            self.stdout.write(self.style.ERROR('Google API key not found. Set GOOGLE_API_KEY environment variable.'))
            return

        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-pro')

    def get_constitutional_data(self):
        """Fetch articles for Part 5 Executive"""
        articles = ConstitutionalArticle.objects.filter(
            part=5,
            type='EXEC'
        ).values('article_number', 'article_title', 'simplified_explanation', 'original_text')
        
        if not articles:
            self.stdout.write(self.style.WARNING('No articles found for Part 5 EXEC'))
            return "", []

        articles_text = "\n\n".join([
            f"Article {art['article_number']}: {art['article_title']}\n"
            f"Explanation: {art['simplified_explanation']}\n"
            f"Original: {art['original_text']}"
            for art in articles
        ])
        return articles_text, articles

    def generate_content_batch(self, articles_text, batch_size=10, max_retries=5):
        """Generate a batch of content variations with retry mechanism"""
        prompt = f"""
        Based on these Constitutional Articles about Part 5 (Executive):

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
        1. Generate exactly {batch_size} items.
        2. Alternate between "Did you know?" facts and concept explanations/explanations of articles.
        3. Each content must be unique and based on the provided articles.
        4. Include article references where applicable.
        5. Keep "Did you know?" facts concise (15-20 words).
        6. Make concept explanations 2-3 sentences long.
        7. Use proper JSON format with double quotes.
        """

        for attempt in range(max_retries):
            try:
                response = self.model.generate_content(
                    prompt,
                    generation_config={
                        'temperature': 0.7,
                        'max_output_tokens': 2048,
                    }
                )
                
                # Attempt JSON extraction
                content_data = json.loads(response.text)
                if 'content' in content_data:
                    return content_data['content'][:batch_size]
            
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'Batch generation error (attempt {attempt + 1}): {str(e)}'))
                time.sleep(2 ** attempt)  # Exponential backoff
            
        self.stdout.write(self.style.ERROR('API failed after retries. Using fallback content.'))
        return [{"content": f"Fallback Fact #{i + 1}", "topic": "Fallback"} for i in range(batch_size)]

    def generate_content_variations(self, articles_text):
        """Generate exactly 80 content variations for normal cells"""
        if not articles_text:
            return []

        all_content = []
        batch_size = 10  # Smaller batches to avoid rate limits
        total_batches = 8  # To reach 80 items

        self.stdout.write('Generating content in batches...')
        
        for i in range(total_batches):
            self.stdout.write(f'Generating batch {i + 1}/{total_batches}...')
            batch_content = self.generate_content_batch(articles_text, batch_size)
            all_content.extend(batch_content)

        # Ensure exactly 80 items
        while len(all_content) < 80:
            all_content.append({"content": f"Extra Fact #{len(all_content) + 1}", "topic": "Extra Content"})

        return all_content[:80]

    def handle(self, *args, **options):
        try:
            self.stdout.write('Fetching Constitutional Articles for Part 5 EXEC...')
            articles_text, articles = self.get_constitutional_data()
            
            if not articles:
                self.stdout.write(self.style.ERROR('No articles found. Aborting.'))
                return

            self.stdout.write('Generating content variations...')
            content_variations = self.generate_content_variations(articles_text)
            
            if not content_variations:
                self.stdout.write(self.style.ERROR('No content generated. Aborting.'))
                return

            self.stdout.write('Creating cells if needed...')
            for number in range(1, 101):
                Cell.objects.get_or_create(number=number)

            self.stdout.write('Creating and mapping content...')
            normal_cells = Cell.objects.exclude(number__in=Cell.SNAKE_LADDER_CELLS)[:80]
            
            for cell, content_data in zip(normal_cells, content_variations):
                cell_content = CellContent.objects.create(
                    content=content_data['content'],
                    topic=content_data['topic'],
                    part=5,
                    type='EXEC'
                )
                cell.contents.add(cell_content)
                cell.current_content = cell_content
                cell.save()

            self.stdout.write(self.style.SUCCESS('Successfully populated cells.'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Unexpected error: {str(e)}'))
            self.stdout.write(traceback.format_exc())
