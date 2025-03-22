import csv
import os
from django.core.management.base import BaseCommand
from dbs.models import ConstitutionalArticle

class Command(BaseCommand):
    help = 'Load constitutional articles from CSV files'

    def get_part_and_type(self, filename):
        # Extract part number and type from filename (e.g., "P6-leg.csv")
        parts = filename.split('-')
        part = int(parts[0][1])  # Extract number after 'P'
        type_map = {
            'leg': 'LEG',
            'exec': 'EXEC',
            'jud': 'JUD'
        }
        type_code = type_map[parts[1].split('.')[0].lower()]
        return part, type_code

    def handle(self, *args, **options):
        # First clear existing data
        ConstitutionalArticle.objects.all().delete()
        
        # List of input files
        files = [
            'P6-leg.csv', 'P5-exec.csv', 'P5-jud.csv',
            'P6-exec.csv', 'P5-leg.csv', 'P6-jud.csv'
        ]
        
        # Get the base directory path (where manage.py is located)
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        
        for filename in files:
            part, type_code = self.get_part_and_type(filename)
            
            # Construct the full path to the data file
            file_path = os.path.join(base_dir, 'data', filename)
            
            # Check if file exists
            if not os.path.exists(file_path):
                self.stdout.write(self.style.WARNING(f'File not found: {file_path}'))
                continue
                
            with open(file_path, 'r', encoding='utf-8') as file:
                csv_reader = csv.reader(file)
                next(csv_reader)  # Skip header row
                
                current_article = None
                article_text = []
                
                for row in csv_reader:
                    if len(row) >= 4:  # Ensure row has all required fields
                        article_number = row[0].strip()
                        article_text = row[1].strip()
                        title = row[2].strip()
                        explanation = row[3].strip()
                        
                        if article_number and not article_number.isspace():
                            # Save previous article if exists
                            if current_article:
                                current_article.save()
                            
                            # Create new article
                            current_article = ConstitutionalArticle(
                                article_number=article_number,
                                article_title=title,
                                original_text=article_text,
                                simplified_explanation=explanation,
                                part=part,
                                type=type_code
                            )
                        else:
                            # Append to existing article text if it's a continuation
                            if current_article:
                                current_article.original_text += "\n" + article_text
                                current_article.simplified_explanation += "\n" + explanation
                
                # Save the last article
                if current_article:
                    current_article.save()
        
        self.stdout.write(self.style.SUCCESS('Successfully loaded constitutional articles')) 