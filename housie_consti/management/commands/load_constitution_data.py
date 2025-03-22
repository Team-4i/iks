import google.generativeai as genai
from django.core.management.base import BaseCommand
from housie_consti.models import Article, Case
import time

class Command(BaseCommand):
    help = 'Load articles and cases from Parts 5 and 6 of the Indian Constitution using Gemini AI'

    def __init__(self):
        super().__init__()
        # Configure Gemini
        genai.configure(api_key='AIzaSyBIZIZoovhNdzrqzh4u71OOfFMiBRi52tk')
        self.model = genai.GenerativeModel('gemini-pro')

    def get_articles_prompt(self, part):
        return f"""
        List all articles from {part} of the Indian Constitution.
        For each article, provide:
        1. Article number
        2. Title
        3. Content (brief explanation)

        Format:
        Article [number]: [title]
        Content: [explanation]

        Focus only on {part} (The Union Judiciary for Part 5, The States for Part 6).
        """

    def get_cases_prompt(self, part):
        return f"""
        Generate 5 real Supreme Court cases related to {part} of the Indian Constitution.
        For each case:
        1. Case title
        2. Year
        3. Constitutional articles involved
        4. Brief description of the case and judgment (2-3 sentences)

        Format each case as:
        Case: [title] ([year])
        Articles: [relevant article numbers]
        Description: [brief description]

        Focus on landmark cases related to {part} (The Union Judiciary for Part 5, The States for Part 6).
        """

    def parse_articles(self, content):
        articles = []
        current_article = {}
        
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('Article'):
                if current_article:
                    articles.append(current_article)
                current_article = {
                    'title': line,
                    'content': ''
                }
            elif line.startswith('Content:'):
                current_article['content'] = line.replace('Content:', '').strip()
        
        if current_article:
            articles.append(current_article)
        
        return articles

    def parse_cases(self, content):
        cases = []
        current_case = {}
        
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('Case:'):
                if current_case:
                    cases.append(current_case)
                current_case = {
                    'title': line.replace('Case:', '').strip(),
                    'description': ''
                }
            elif line.startswith('Description:'):
                current_case['description'] = line.replace('Description:', '').strip()
        
        if current_case:
            cases.append(current_case)
        
        return cases

    def handle(self, *args, **options):
        parts = ['Part 5', 'Part 6']
        
        # Load articles for each part
        for part in parts:
            self.stdout.write(f'Fetching articles for {part}...')
            response = self.model.generate_content(self.get_articles_prompt(part))
            articles_data = self.parse_articles(response.text)
            
            for article_data in articles_data:
                article = Article.objects.create(
                    title=article_data['title'],
                    content=article_data['content']
                )
                self.stdout.write(f'Created article: {article.title}')
            
            # Add delay to respect rate limits
            time.sleep(2)

        # Load cases for each part
        total_cases = 0
        while total_cases < 50:  # Generate cases until we have 50
            for part in parts:
                self.stdout.write(f'Fetching cases for {part}...')
                response = self.model.generate_content(self.get_cases_prompt(part))
                cases_data = self.parse_cases(response.text)
                
                for case_data in cases_data:
                    # Get a random article from the corresponding part
                    article = Article.objects.filter(title__contains=part).order_by('?').first()
                    if article:
                        case = Case.objects.create(
                            article=article,
                            description=case_data['description']
                        )
                        self.stdout.write(f'Created case: {case_data["title"]}')
                        total_cases += 1
                        
                        if total_cases >= 50:
                            break
                
                # Add delay to respect rate limits
                time.sleep(2)
                
                if total_cases >= 50:
                    break

        self.stdout.write(self.style.SUCCESS(f'Successfully loaded {Article.objects.count()} articles and {Case.objects.count()} cases.'))

# To run this script, save it as a management command in your Django app.