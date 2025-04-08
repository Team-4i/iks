import csv
from django.core.management.base import BaseCommand
from snake_ladder.models import GameFact

class Command(BaseCommand):
    help = 'Import facts from a CSV file into the GameFact model'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the CSV file containing facts')

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        
        try:
            with open(csv_file, 'r', encoding='utf-8') as file:
                csv_reader = csv.reader(file)
                
                # Skip header row if it exists
                header = next(csv_reader, None)
                
                # Count for reporting
                count = 0
                
                # Process each row
                for row in csv_reader:
                    if row and row[0].strip():  # Check if row is not empty
                        fact_text = row[0].strip()
                        
                        # Create new fact
                        GameFact.objects.create(fact_text=fact_text)
                        count += 1
                
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully imported {count} facts from {csv_file}')
                )
                
        except FileNotFoundError:
            self.stdout.write(
                self.style.ERROR(f'File not found: {csv_file}')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error importing facts: {str(e)}')
            ) 