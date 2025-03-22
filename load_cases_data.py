import google.generativeai as genai
from django.core.management.base import BaseCommand
from housie_consti.models import Article, Case
import time
import re

class Command(BaseCommand):
    help = 'Load Supreme Court cases related to Parts 5 and 6 of the Indian Constitution using Gemini AI'

    def __init__(self):
        super().__init__()
        genai.configure(api_key='AIzaSyBIZIZoovhNdzrqzh4u71OOfFMiBRi52tk')
        self.model = genai.GenerativeModel('gemini-pro')

    def extract_year(self, title):
        match = re.search(r'\((\d{4})\)', title)
        if match:
            return int(match.group(1))
        return 2024

    def parse_cases(self, content):
        cases = []
        current_case = {}
        
        for line in content.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            if '**Case:**' in line or 'Case:' in line:
                if current_case and 'title' in current_case and 'description' in current_case:
                    cases.append(current_case)
                
                title = line.replace('**Case:**', '').replace('Case:', '').strip()
                title = re.sub(r'^\d+\.\s*', '', title)
                
                current_case = {
                    'title': title,
                    'year': self.extract_year(title),
                    'description': ''
                }
            elif '**Description:**' in line or 'Description:' in line:
                current_case['description'] = line.replace('**Description:**', '').replace('Description:', '').strip()
        
        if current_case and 'title' in current_case and 'description' in current_case:
            cases.append(current_case)
        
        return cases

    def get_cases_for_part(self, part_number):
        prompt = f"""Give me 10 real Supreme Court cases related to Part {part_number} of the Indian Constitution.
        For Part {part_number} - {'The Union Judiciary' if part_number == 5 else 'The States'}
        
        Format each case as:
        Case: [Full case name] ([year])
        Description: [2-3 sentences about the case and its significance]
        
        Note: Please provide significant cases that specifically deal with Part {part_number}.
        """
        
        response = self.model.generate_content(prompt)
        if not response.text:
            raise Exception("Empty response from API")
        
        return self.parse_cases(response.text)

    def handle(self, *args, **options):
        # Get existing cases count
        existing_count = Case.objects.count()
        self.stdout.write(f'Found {existing_count} existing cases')

        # Get all articles from database
        articles = Article.objects.all()
        if not articles.exists():
            self.stdout.write(self.style.ERROR('No articles found in database. Please load articles first.'))
            return

        # Process each part
        for part_number in [5, 6]:
            self.stdout.write(f'\nFetching cases for Part {part_number}...')
            
            try:
                cases_data = self.get_cases_for_part(part_number)
                
                for case_data in cases_data:
                    try:
                        # Randomly assign an article from our database
                        article = articles.order_by('?').first()
                        
                        new_case = Case.objects.create(
                            article=article,
                            title=case_data['title'],
                            description=case_data['description']
                        )
                        self.stdout.write(f'Created case: {new_case.title} (Associated with Article: {article.title})')
                        
                    except Exception as create_error:
                        self.stdout.write(self.style.ERROR(f'Error creating case: {str(create_error)}'))
                
                time.sleep(2)  # Respect API rate limits
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error for Part {part_number}: {str(e)}'))
                time.sleep(5)  # Longer delay on error
                continue

        # Print final statistics
        final_count = Case.objects.count()
        self.stdout.write(self.style.SUCCESS(f'\nProcess completed. Added {final_count - existing_count} new cases'))

        # Print all cases for verification
        self.stdout.write('\nAll loaded cases:')
        for case in Case.objects.all():
            self.stdout.write('\n' + '-'*50)
            self.stdout.write(f'Title: {case.title}')
            self.stdout.write(f'Associated Article: {case.article.title}')
            self.stdout.write(f'Description: {case.description}') 