import os
import pandas as pd
import json
from datetime import datetime
from django.core.management.base import BaseCommand
from django.db import transaction
from hang.models import (
    QuestionCategory, MCQQuestion, FillBlankQuestion, 
    MatchPairsQuestion, TrueFalseQuestion, OddOneOutQuestion,
    CategorizeQuestion, WordUnscrambleQuestion,
    MainTopic, SubTopic, Topic, Chapter
)

class Command(BaseCommand):
    help = 'Import questions from an Excel file previously exported with export_questions command'

    def add_arguments(self, parser):
        parser.add_argument(
            'input_file',
            type=str,
            help='Path to the Excel file to import'
        )
        parser.add_argument(
            '--update',
            action='store_true',
            help='Update existing questions if they exist (based on ID)'
        )
        parser.add_argument(
            '--category_id',
            type=int,
            help='Import questions only for a specific category',
            required=False
        )

    def handle(self, *args, **options):
        input_file = options['input_file']
        update_existing = options.get('update', False)
        category_id = options.get('category_id')
        
        if not os.path.exists(input_file):
            self.stdout.write(self.style.ERROR(f'File not found: {input_file}'))
            return
        
        try:
            # Load Excel file
            self.stdout.write(f'Reading file: {input_file}')
            xl = pd.ExcelFile(input_file)
            
            # Check if we have the Categories Summary sheet
            if 'Categories Summary' not in xl.sheet_names:
                self.stdout.write(self.style.WARNING('Categories Summary sheet not found. Categories might not be imported correctly.'))
            else:
                # Import categories first
                self.import_categories(xl, category_id)
            
            # Import questions
            with transaction.atomic():
                if 'MCQ Questions' in xl.sheet_names:
                    self.import_mcq_questions(xl, update_existing, category_id)
                
                if 'Fill Questions' in xl.sheet_names:
                    self.import_fill_questions(xl, update_existing, category_id)
                
                if 'Match Questions' in xl.sheet_names:
                    self.import_match_questions(xl, update_existing, category_id)
                
                if 'TF Questions' in xl.sheet_names:
                    self.import_tf_questions(xl, update_existing, category_id)
                
                if 'Odd Questions' in xl.sheet_names:
                    self.import_odd_questions(xl, update_existing, category_id)
                
                if 'Categorize Questions' in xl.sheet_names:
                    self.import_categorize_questions(xl, update_existing, category_id)
                
                if 'Scramble Questions' in xl.sheet_names:
                    self.import_scramble_questions(xl, update_existing, category_id)
            
            self.stdout.write(self.style.SUCCESS('Import completed successfully'))
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error importing questions: {str(e)}'))
    
    def import_categories(self, xl, category_id=None):
        """Import categories from the summary sheet"""
        self.stdout.write('Importing categories...')
        
        try:
            df = pd.read_excel(xl, 'Categories Summary')
            
            count = 0
            for _, row in df.iterrows():
                if category_id and row['id'] != category_id:
                    continue
                    
                obj, created = QuestionCategory.objects.update_or_create(
                    id=row['id'],
                    defaults={
                        'name': row['name'],
                        'description': row['description']
                    }
                )
                
                if created:
                    self.stdout.write(f"  Created category: {row['name']}")
                else:
                    self.stdout.write(f"  Updated category: {row['name']}")
                    
                count += 1
            
            self.stdout.write(f'  Imported {count} categories')
        
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Error importing categories: {str(e)}'))
    
    def get_source_references(self, row):
        """Get or create source reference objects from a row"""
        main_topic = None
        sub_topic = None
        topic = None
        chapter = None
        
        # Create or get main topic if specified
        if pd.notna(row.get('main_topic_id')) and pd.notna(row.get('main_topic_name')):
            main_topic, _ = MainTopic.objects.get_or_create(
                id=row['main_topic_id'],
                defaults={'title': row['main_topic_name']}
            )
        
        # Create or get sub topic if specified
        if pd.notna(row.get('sub_topic_id')) and pd.notna(row.get('sub_topic_name')):
            sub_topic, _ = SubTopic.objects.get_or_create(
                id=row['sub_topic_id'],
                defaults={'title': row['sub_topic_name']}
            )
        
        # Create or get topic if specified
        if pd.notna(row.get('topic_id')) and pd.notna(row.get('topic_name')):
            topic, _ = Topic.objects.get_or_create(
                id=row['topic_id'],
                defaults={'title': row['topic_name']}
            )
        
        # Create or get chapter if specified
        if pd.notna(row.get('chapter_id')) and pd.notna(row.get('chapter_name')):
            chapter, _ = Chapter.objects.get_or_create(
                id=row['chapter_id'],
                defaults={'title': row['chapter_name']}
            )
        
        return main_topic, sub_topic, topic, chapter
    
    def get_category(self, category_id):
        """Get a category by ID"""
        try:
            return QuestionCategory.objects.get(id=category_id)
        except QuestionCategory.DoesNotExist:
            self.stdout.write(self.style.WARNING(f'Category with ID {category_id} not found'))
            return None
    
    def import_mcq_questions(self, xl, update_existing, category_filter=None):
        """Import Multiple Choice Questions"""
        self.stdout.write('Importing MCQ questions...')
        
        df = pd.read_excel(xl, 'MCQ Questions')
        
        if category_filter:
            df = df[df['category_id'] == category_filter]
        
        created_count = 0
        updated_count = 0
        
        for _, row in df.iterrows():
            if not self.get_category(row['category_id']):
                continue
            
            # Get or create source references
            main_topic, sub_topic, topic, chapter = self.get_source_references(row)
            
            # Parse options from JSON string
            options = json.loads(row['options'])
            
            # Prepare data dictionary
            data = {
                'category_id': row['category_id'],
                'question_text': row['question_text'],
                'options': options,
                'correct_answer': row['correct_answer'],
                'difficulty': row['difficulty'],
                'is_active': row['is_active'],
                'question_type': 'MCQ',
                'main_topic': main_topic,
                'sub_topic': sub_topic,
                'topic': topic,
                'chapter': chapter
            }
            
            # Create or update question
            if update_existing:
                question, created = MCQQuestion.objects.update_or_create(
                    id=row['id'],
                    defaults=data
                )
                if created:
                    created_count += 1
                else:
                    updated_count += 1
            else:
                # Only create if doesn't exist
                if not MCQQuestion.objects.filter(id=row['id']).exists():
                    MCQQuestion.objects.create(id=row['id'], **data)
                    created_count += 1
                else:
                    self.stdout.write(f"  Skipped MCQ question ID {row['id']} (already exists)")
        
        self.stdout.write(f'  Created {created_count} MCQ questions')
        if update_existing:
            self.stdout.write(f'  Updated {updated_count} MCQ questions')
    
    def import_fill_questions(self, xl, update_existing, category_filter=None):
        """Import Fill in the Blank Questions"""
        self.stdout.write('Importing Fill in the Blank questions...')
        
        df = pd.read_excel(xl, 'Fill Questions')
        
        if category_filter:
            df = df[df['category_id'] == category_filter]
        
        created_count = 0
        updated_count = 0
        
        for _, row in df.iterrows():
            if not self.get_category(row['category_id']):
                continue
            
            # Get or create source references
            main_topic, sub_topic, topic, chapter = self.get_source_references(row)
            
            # Prepare data dictionary
            data = {
                'category_id': row['category_id'],
                'question_text': row['question_text'],
                'answer': row['answer'],
                'hint_pattern': row['hint_pattern'],
                'difficulty': row['difficulty'],
                'is_active': row['is_active'],
                'question_type': 'FILL',
                'main_topic': main_topic,
                'sub_topic': sub_topic,
                'topic': topic,
                'chapter': chapter
            }
            
            # Create or update question
            if update_existing:
                question, created = FillBlankQuestion.objects.update_or_create(
                    id=row['id'],
                    defaults=data
                )
                if created:
                    created_count += 1
                else:
                    updated_count += 1
            else:
                # Only create if doesn't exist
                if not FillBlankQuestion.objects.filter(id=row['id']).exists():
                    FillBlankQuestion.objects.create(id=row['id'], **data)
                    created_count += 1
                else:
                    self.stdout.write(f"  Skipped Fill question ID {row['id']} (already exists)")
        
        self.stdout.write(f'  Created {created_count} Fill in the Blank questions')
        if update_existing:
            self.stdout.write(f'  Updated {updated_count} Fill in the Blank questions')
    
    def import_match_questions(self, xl, update_existing, category_filter=None):
        """Import Matching Pairs Questions"""
        self.stdout.write('Importing Matching Pairs questions...')
        
        df = pd.read_excel(xl, 'Match Questions')
        
        if category_filter:
            df = df[df['category_id'] == category_filter]
        
        created_count = 0
        updated_count = 0
        
        for _, row in df.iterrows():
            if not self.get_category(row['category_id']):
                continue
            
            # Get or create source references
            main_topic, sub_topic, topic, chapter = self.get_source_references(row)
            
            # Parse pairs from JSON string
            pairs = json.loads(row['pairs'])
            
            # Prepare data dictionary
            data = {
                'category_id': row['category_id'],
                'question_text': row['question_text'],
                'pairs': pairs,
                'difficulty': row['difficulty'],
                'is_active': row['is_active'],
                'question_type': 'MATCH',
                'main_topic': main_topic,
                'sub_topic': sub_topic,
                'topic': topic,
                'chapter': chapter
            }
            
            # Create or update question
            if update_existing:
                question, created = MatchPairsQuestion.objects.update_or_create(
                    id=row['id'],
                    defaults=data
                )
                if created:
                    created_count += 1
                else:
                    updated_count += 1
            else:
                # Only create if doesn't exist
                if not MatchPairsQuestion.objects.filter(id=row['id']).exists():
                    MatchPairsQuestion.objects.create(id=row['id'], **data)
                    created_count += 1
                else:
                    self.stdout.write(f"  Skipped Match question ID {row['id']} (already exists)")
        
        self.stdout.write(f'  Created {created_count} Matching Pairs questions')
        if update_existing:
            self.stdout.write(f'  Updated {updated_count} Matching Pairs questions')
    
    def import_tf_questions(self, xl, update_existing, category_filter=None):
        """Import True/False Questions"""
        self.stdout.write('Importing True/False questions...')
        
        df = pd.read_excel(xl, 'TF Questions')
        
        if category_filter:
            df = df[df['category_id'] == category_filter]
        
        created_count = 0
        updated_count = 0
        
        for _, row in df.iterrows():
            if not self.get_category(row['category_id']):
                continue
            
            # Get or create source references
            main_topic, sub_topic, topic, chapter = self.get_source_references(row)
            
            # Convert string 'true'/'false' to boolean
            correct_answer = row['correct_answer'].lower() == 'true' if isinstance(row['correct_answer'], str) else bool(row['correct_answer'])
            
            # Prepare data dictionary
            data = {
                'category_id': row['category_id'],
                'question_text': row['question_text'],
                'correct_answer': correct_answer,
                'difficulty': row['difficulty'],
                'is_active': row['is_active'],
                'question_type': 'TF',
                'main_topic': main_topic,
                'sub_topic': sub_topic,
                'topic': topic,
                'chapter': chapter
            }
            
            # Create or update question
            if update_existing:
                question, created = TrueFalseQuestion.objects.update_or_create(
                    id=row['id'],
                    defaults=data
                )
                if created:
                    created_count += 1
                else:
                    updated_count += 1
            else:
                # Only create if doesn't exist
                if not TrueFalseQuestion.objects.filter(id=row['id']).exists():
                    TrueFalseQuestion.objects.create(id=row['id'], **data)
                    created_count += 1
                else:
                    self.stdout.write(f"  Skipped TF question ID {row['id']} (already exists)")
        
        self.stdout.write(f'  Created {created_count} True/False questions')
        if update_existing:
            self.stdout.write(f'  Updated {updated_count} True/False questions')
    
    def import_odd_questions(self, xl, update_existing, category_filter=None):
        """Import Odd One Out Questions"""
        self.stdout.write('Importing Odd One Out questions...')
        
        df = pd.read_excel(xl, 'Odd Questions')
        
        if category_filter:
            df = df[df['category_id'] == category_filter]
        
        created_count = 0
        updated_count = 0
        
        for _, row in df.iterrows():
            if not self.get_category(row['category_id']):
                continue
            
            # Get or create source references
            main_topic, sub_topic, topic, chapter = self.get_source_references(row)
            
            # Parse options from JSON string
            options = json.loads(row['options'])
            
            # Handle missing explanation field
            explanation = row.get('explanation', '')
            
            # Prepare data dictionary
            data = {
                'category_id': row['category_id'],
                'question_text': row['question_text'],
                'options': options,
                'correct_answer': row['correct_answer'],
                'explanation': explanation,
                'difficulty': row['difficulty'],
                'is_active': row['is_active'],
                'question_type': 'ODD',
                'main_topic': main_topic,
                'sub_topic': sub_topic,
                'topic': topic,
                'chapter': chapter
            }
            
            # Create or update question
            if update_existing:
                question, created = OddOneOutQuestion.objects.update_or_create(
                    id=row['id'],
                    defaults=data
                )
                if created:
                    created_count += 1
                else:
                    updated_count += 1
            else:
                # Only create if doesn't exist
                if not OddOneOutQuestion.objects.filter(id=row['id']).exists():
                    OddOneOutQuestion.objects.create(id=row['id'], **data)
                    created_count += 1
                else:
                    self.stdout.write(f"  Skipped Odd question ID {row['id']} (already exists)")
        
        self.stdout.write(f'  Created {created_count} Odd One Out questions')
        if update_existing:
            self.stdout.write(f'  Updated {updated_count} Odd One Out questions')
    
    def import_categorize_questions(self, xl, update_existing, category_filter=None):
        """Import Categorize Questions"""
        self.stdout.write('Importing Categorize questions...')
        
        df = pd.read_excel(xl, 'Categorize Questions')
        
        if category_filter:
            df = df[df['category_id'] == category_filter]
        
        created_count = 0
        updated_count = 0
        
        for _, row in df.iterrows():
            if not self.get_category(row['category_id']):
                continue
            
            # Get or create source references
            main_topic, sub_topic, topic, chapter = self.get_source_references(row)
            
            # Parse categories and items from JSON strings
            categories = json.loads(row['categories'])
            items = json.loads(row['items'])
            
            # Prepare data dictionary
            data = {
                'category_id': row['category_id'],
                'question_text': row['question_text'],
                'categories': categories,
                'items': items,
                'difficulty': row['difficulty'],
                'is_active': row['is_active'],
                'question_type': 'CAT',
                'main_topic': main_topic,
                'sub_topic': sub_topic,
                'topic': topic,
                'chapter': chapter
            }
            
            # Create or update question
            if update_existing:
                question, created = CategorizeQuestion.objects.update_or_create(
                    id=row['id'],
                    defaults=data
                )
                if created:
                    created_count += 1
                else:
                    updated_count += 1
            else:
                # Only create if doesn't exist
                if not CategorizeQuestion.objects.filter(id=row['id']).exists():
                    CategorizeQuestion.objects.create(id=row['id'], **data)
                    created_count += 1
                else:
                    self.stdout.write(f"  Skipped Categorize question ID {row['id']} (already exists)")
        
        self.stdout.write(f'  Created {created_count} Categorize questions')
        if update_existing:
            self.stdout.write(f'  Updated {updated_count} Categorize questions')
    
    def import_scramble_questions(self, xl, update_existing, category_filter=None):
        """Import Word Unscramble Questions"""
        self.stdout.write('Importing Word Unscramble questions...')
        
        df = pd.read_excel(xl, 'Scramble Questions')
        
        if category_filter:
            df = df[df['category_id'] == category_filter]
        
        created_count = 0
        updated_count = 0
        
        for _, row in df.iterrows():
            if not self.get_category(row['category_id']):
                continue
            
            # Get or create source references
            main_topic, sub_topic, topic, chapter = self.get_source_references(row)
            
            # Handle missing hint field
            hint = row.get('hint', '')
            
            # Prepare data dictionary
            data = {
                'category_id': row['category_id'],
                'question_text': row['question_text'],
                'scrambled_word': row['scrambled_word'],
                'correct_word': row['correct_word'],
                'hint': hint,
                'difficulty': row['difficulty'],
                'is_active': row['is_active'],
                'question_type': 'SCRAMBLE',
                'main_topic': main_topic,
                'sub_topic': sub_topic,
                'topic': topic,
                'chapter': chapter
            }
            
            # Create or update question
            if update_existing:
                question, created = WordUnscrambleQuestion.objects.update_or_create(
                    id=row['id'],
                    defaults=data
                )
                if created:
                    created_count += 1
                else:
                    updated_count += 1
            else:
                # Only create if doesn't exist
                if not WordUnscrambleQuestion.objects.filter(id=row['id']).exists():
                    WordUnscrambleQuestion.objects.create(id=row['id'], **data)
                    created_count += 1
                else:
                    self.stdout.write(f"  Skipped Scramble question ID {row['id']} (already exists)")
        
        self.stdout.write(f'  Created {created_count} Word Unscramble questions')
        if update_existing:
            self.stdout.write(f'  Updated {updated_count} Word Unscramble questions') 


#             # Import all questions from an Excel file
# python manage.py import_questions hangman_questions_export_20250419_033927.xlsx

# # Import and update existing questions
# python manage.py import_questions hangman_questions_export_20250419_033927.xlsx --update

# # Import questions for a specific category only
# python manage.py import_questions hangman_questions_export_20250419_033927.xlsx --category_id 1