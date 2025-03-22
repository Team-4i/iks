import google.generativeai as genai
from django.core.management.base import BaseCommand
from housie_consti.models import Article, Case
import time
import re

class Command(BaseCommand):
    help = 'Load Supreme Court cases for articles that do not have associated cases'

    def __init__(self):
        super().__init__()
        genai.configure(api_key='AIzaSyDNQHOszQYJxJRwVJPcKMj3no4wQ6DREO8')
        self.model = genai.GenerativeModel('gemini-pro')

    def parse_cases(self, content):
        """Parse the case data with improved reliability."""
        cases = []
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        
        current_case = {}
        for i, line in enumerate(lines):
            line = re.sub(r'^\d+\.\s*', '', line)
            
            if line.lower().startswith(('case:', '**case:**')):
                if current_case and 'title' in current_case and 'description' in current_case:
                    cases.append(current_case)
                    current_case = {}
                
                title = re.sub(r'^case:|\*\*case:\*\*', '', line, flags=re.IGNORECASE).strip()
                current_case['title'] = title
                
            elif line.lower().startswith(('description:', '**description:**')):
                desc = re.sub(r'^description:|\*\*description:\*\*', '', line, flags=re.IGNORECASE).strip()
                current_case['description'] = desc
        
        if current_case and 'title' in current_case and 'description' in current_case:
            cases.append(current_case)
        
        return cases[:1]

    def get_cases_for_article(self, article):
        """Generate one case specifically for a given article."""
        prompt = f"""Give me exactly 1 real Supreme Court case related to Article {article.article_number} of the Indian Constitution.
        Article {article.article_number}: {article.title}
        
        Format the case exactly as follows (include the labels):
        Case: [Full case name] ([year])
        Description: [2-3 sentences about the case and its significance]
        
        Note: Please provide a significant case that specifically deals with Article {article.article_number}.
        """
        
        response = self.model.generate_content(prompt)
        if not response.text:
            raise Exception("Empty response from API")
        
        return self.parse_cases(response.text)

    def handle(self, *args, **options):
        # Get articles without cases - using correct related name 'cases'
        articles_without_cases = Article.objects.filter(cases__isnull=True)
        total_remaining = articles_without_cases.count()

        if total_remaining == 0:
            self.stdout.write(self.style.SUCCESS('All articles have associated cases!'))
            return

        self.stdout.write(f'Found {total_remaining} articles without cases')
        successful_cases = 0

        # Process each remaining article
        for article in articles_without_cases:
            self.stdout.write(f'\nFetching case for Article {article.article_number}...')
            
            try:
                cases_data = self.get_cases_for_article(article)
                
                if cases_data:
                    case_data = cases_data[0]
                    try:
                        new_case = Case.objects.create(
                            title=case_data['title'],
                            description=case_data['description']
                        )
                        new_case.articles.add(article)
                        successful_cases += 1
                        
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'Created case: {new_case.title}\n'
                                f'Associated Article: {article.article_number}'
                            )
                        )
                        
                    except Exception as create_error:
                        self.stdout.write(self.style.ERROR(f'Error creating case: {str(create_error)}'))
                
                time.sleep(2)  # Respect API rate limits
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error for Article {article.article_number}: {str(e)}'))
                time.sleep(5)  # Longer delay on error
                continue

        # Print final statistics
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS(
            f'Process completed.\n'
            f'Total articles without cases: {total_remaining}\n'
            f'Successfully created cases: {successful_cases}\n'
            f'Failed cases: {total_remaining - successful_cases}'
        )) 