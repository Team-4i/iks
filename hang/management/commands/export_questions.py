import os
import pandas as pd
from datetime import datetime
from django.core.management.base import BaseCommand
from hang.models import (
    QuestionCategory, MCQQuestion, FillBlankQuestion, 
    MatchPairsQuestion, TrueFalseQuestion, OddOneOutQuestion,
    CategorizeQuestion, WordUnscrambleQuestion
)
import json
from django.utils.timezone import make_naive, is_aware

class Command(BaseCommand):
    help = 'Export all hangman questions to an Excel file for backup and future import'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            default='hangman_questions_export',
            help='Base name for the output Excel file (without extension)',
            required=False
        )
        parser.add_argument(
            '--category_id',
            type=int,
            help='Export questions for a specific category only',
            required=False
        )

    def handle(self, *args, **options):
        output_base = options.get('output')
        category_id = options.get('category_id')
        
        # Create an export timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = f"{output_base}_{timestamp}.xlsx"
        
        # Create Excel writer
        writer = pd.ExcelWriter(output_file, engine='xlsxwriter')
        
        # Filter categories if needed
        if category_id:
            categories = QuestionCategory.objects.filter(id=category_id)
            self.stdout.write(f"Exporting questions for category ID: {category_id}")
        else:
            categories = QuestionCategory.objects.all()
            self.stdout.write(f"Exporting questions for all categories")
        
        # Export each question type
        self.export_mcq_questions(writer, categories)
        self.export_fill_questions(writer, categories)
        self.export_match_questions(writer, categories)
        self.export_tf_questions(writer, categories)
        self.export_odd_questions(writer, categories)
        self.export_cat_questions(writer, categories)
        self.export_scramble_questions(writer, categories)
        
        # Create a summary sheet with category info
        self.export_categories_summary(writer, categories)
        
        # Save Excel file
        writer.close()
        
        self.stdout.write(self.style.SUCCESS(f'Successfully exported questions to {output_file}'))

    def convert_timezone_aware_dates(self, date_obj):
        """Convert timezone aware datetime objects to naive"""
        if date_obj and is_aware(date_obj):
            return make_naive(date_obj)
        return date_obj

    def export_mcq_questions(self, writer, categories):
        """Export Multiple Choice Questions"""
        self.stdout.write('Exporting MCQ questions...')
        
        # Get MCQ questions for the specified categories
        mcq_questions = MCQQuestion.objects.filter(category__in=categories)
        
        if not mcq_questions.exists():
            self.stdout.write('  No MCQ questions found')
            return
        
        # Create a dataframe for MCQ questions
        data = []
        for q in mcq_questions:
            # Convert options from JSON to string
            options_str = json.dumps(q.options)
            
            # Get source info
            main_topic_name = q.main_topic.title if q.main_topic else None
            sub_topic_name = q.sub_topic.title if q.sub_topic else None
            topic_name = q.topic.title if q.topic else None
            chapter_name = q.chapter.title if q.chapter else None
            
            # Convert timezone-aware dates to naive
            created_at = self.convert_timezone_aware_dates(q.created_at)
            updated_at = self.convert_timezone_aware_dates(q.updated_at)
            
            # Add to data
            data.append({
                'id': q.id,
                'category_id': q.category_id,
                'category_name': q.category.name,
                'question_text': q.question_text,
                'options': options_str,
                'correct_answer': q.correct_answer,
                'difficulty': q.difficulty,
                'is_active': q.is_active,
                'main_topic_id': q.main_topic_id,
                'main_topic_name': main_topic_name,
                'sub_topic_id': q.sub_topic_id,
                'sub_topic_name': sub_topic_name,
                'topic_id': q.topic_id,
                'topic_name': topic_name,
                'chapter_id': q.chapter_id,
                'chapter_name': chapter_name,
                'created_at': created_at,
                'updated_at': updated_at
            })
        
        # Create dataframe and export to Excel
        df = pd.DataFrame(data)
        df.to_excel(writer, sheet_name='MCQ Questions', index=False)
        self.stdout.write(f'  Exported {len(data)} MCQ questions')

    def export_fill_questions(self, writer, categories):
        """Export Fill in the Blank Questions"""
        self.stdout.write('Exporting Fill in the Blank questions...')
        
        # Get Fill questions for the specified categories
        fill_questions = FillBlankQuestion.objects.filter(category__in=categories)
        
        if not fill_questions.exists():
            self.stdout.write('  No Fill in the Blank questions found')
            return
        
        # Create a dataframe for Fill questions
        data = []
        for q in fill_questions:
            # Get source info
            main_topic_name = q.main_topic.title if q.main_topic else None
            sub_topic_name = q.sub_topic.title if q.sub_topic else None
            topic_name = q.topic.title if q.topic else None
            chapter_name = q.chapter.title if q.chapter else None
            
            # Convert timezone-aware dates to naive
            created_at = self.convert_timezone_aware_dates(q.created_at)
            updated_at = self.convert_timezone_aware_dates(q.updated_at)
            
            # Add to data
            data.append({
                'id': q.id,
                'category_id': q.category_id,
                'category_name': q.category.name,
                'question_text': q.question_text,
                'answer': q.answer,
                'hint_pattern': q.hint_pattern,
                'difficulty': q.difficulty,
                'is_active': q.is_active,
                'main_topic_id': q.main_topic_id,
                'main_topic_name': main_topic_name,
                'sub_topic_id': q.sub_topic_id,
                'sub_topic_name': sub_topic_name,
                'topic_id': q.topic_id,
                'topic_name': topic_name,
                'chapter_id': q.chapter_id,
                'chapter_name': chapter_name,
                'created_at': created_at,
                'updated_at': updated_at
            })
        
        # Create dataframe and export to Excel
        df = pd.DataFrame(data)
        df.to_excel(writer, sheet_name='Fill Questions', index=False)
        self.stdout.write(f'  Exported {len(data)} Fill in the Blank questions')

    def export_match_questions(self, writer, categories):
        """Export Matching Pairs Questions"""
        self.stdout.write('Exporting Matching Pairs questions...')
        
        # Get Match questions for the specified categories
        match_questions = MatchPairsQuestion.objects.filter(category__in=categories)
        
        if not match_questions.exists():
            self.stdout.write('  No Matching Pairs questions found')
            return
        
        # Create a dataframe for Match questions
        data = []
        for q in match_questions:
            # Convert pairs from JSON to string
            pairs_str = json.dumps(q.pairs)
            
            # Get source info
            main_topic_name = q.main_topic.title if q.main_topic else None
            sub_topic_name = q.sub_topic.title if q.sub_topic else None
            topic_name = q.topic.title if q.topic else None
            chapter_name = q.chapter.title if q.chapter else None
            
            # Convert timezone-aware dates to naive
            created_at = self.convert_timezone_aware_dates(q.created_at)
            updated_at = self.convert_timezone_aware_dates(q.updated_at)
            
            # Add to data
            data.append({
                'id': q.id,
                'category_id': q.category_id,
                'category_name': q.category.name,
                'question_text': q.question_text,
                'pairs': pairs_str,
                'difficulty': q.difficulty,
                'is_active': q.is_active,
                'main_topic_id': q.main_topic_id,
                'main_topic_name': main_topic_name,
                'sub_topic_id': q.sub_topic_id,
                'sub_topic_name': sub_topic_name,
                'topic_id': q.topic_id,
                'topic_name': topic_name,
                'chapter_id': q.chapter_id,
                'chapter_name': chapter_name,
                'created_at': created_at,
                'updated_at': updated_at
            })
        
        # Create dataframe and export to Excel
        df = pd.DataFrame(data)
        df.to_excel(writer, sheet_name='Match Questions', index=False)
        self.stdout.write(f'  Exported {len(data)} Matching Pairs questions')

    def export_tf_questions(self, writer, categories):
        """Export True/False Questions"""
        self.stdout.write('Exporting True/False questions...')
        
        # Get T/F questions for the specified categories
        tf_questions = TrueFalseQuestion.objects.filter(category__in=categories)
        
        if not tf_questions.exists():
            self.stdout.write('  No True/False questions found')
            return
        
        # Create a dataframe for T/F questions
        data = []
        for q in tf_questions:
            # Get source info
            main_topic_name = q.main_topic.title if q.main_topic else None
            sub_topic_name = q.sub_topic.title if q.sub_topic else None
            topic_name = q.topic.title if q.topic else None
            chapter_name = q.chapter.title if q.chapter else None
            
            # Convert timezone-aware dates to naive
            created_at = self.convert_timezone_aware_dates(q.created_at)
            updated_at = self.convert_timezone_aware_dates(q.updated_at)
            
            # Add to data
            data.append({
                'id': q.id,
                'category_id': q.category_id,
                'category_name': q.category.name,
                'question_text': q.question_text,
                'correct_answer': 'true' if q.correct_answer else 'false',
                'difficulty': q.difficulty,
                'is_active': q.is_active,
                'main_topic_id': q.main_topic_id,
                'main_topic_name': main_topic_name,
                'sub_topic_id': q.sub_topic_id,
                'sub_topic_name': sub_topic_name,
                'topic_id': q.topic_id,
                'topic_name': topic_name,
                'chapter_id': q.chapter_id,
                'chapter_name': chapter_name,
                'created_at': created_at,
                'updated_at': updated_at
            })
        
        # Create dataframe and export to Excel
        df = pd.DataFrame(data)
        df.to_excel(writer, sheet_name='TF Questions', index=False)
        self.stdout.write(f'  Exported {len(data)} True/False questions')

    def export_odd_questions(self, writer, categories):
        """Export Odd One Out Questions"""
        self.stdout.write('Exporting Odd One Out questions...')
        
        # Get Odd questions for the specified categories
        odd_questions = OddOneOutQuestion.objects.filter(category__in=categories)
        
        if not odd_questions.exists():
            self.stdout.write('  No Odd One Out questions found')
            return
        
        # Create a dataframe for Odd questions
        data = []
        for q in odd_questions:
            # Convert options from JSON to string
            options_str = json.dumps(q.options)
            
            # Get source info
            main_topic_name = q.main_topic.title if q.main_topic else None
            sub_topic_name = q.sub_topic.title if q.sub_topic else None
            topic_name = q.topic.title if q.topic else None
            chapter_name = q.chapter.title if q.chapter else None
            
            # Convert timezone-aware dates to naive
            created_at = self.convert_timezone_aware_dates(q.created_at)
            updated_at = self.convert_timezone_aware_dates(q.updated_at)
            
            # Add to data
            data.append({
                'id': q.id,
                'category_id': q.category_id,
                'category_name': q.category.name,
                'question_text': q.question_text,
                'options': options_str,
                'correct_answer': q.correct_answer,
                'explanation': q.explanation,
                'difficulty': q.difficulty,
                'is_active': q.is_active,
                'main_topic_id': q.main_topic_id,
                'main_topic_name': main_topic_name,
                'sub_topic_id': q.sub_topic_id,
                'sub_topic_name': sub_topic_name,
                'topic_id': q.topic_id,
                'topic_name': topic_name,
                'chapter_id': q.chapter_id,
                'chapter_name': chapter_name,
                'created_at': created_at,
                'updated_at': updated_at
            })
        
        # Create dataframe and export to Excel
        df = pd.DataFrame(data)
        df.to_excel(writer, sheet_name='Odd Questions', index=False)
        self.stdout.write(f'  Exported {len(data)} Odd One Out questions')

    def export_cat_questions(self, writer, categories):
        """Export Categorize Questions"""
        self.stdout.write('Exporting Categorize questions...')
        
        # Get Categorize questions for the specified categories
        cat_questions = CategorizeQuestion.objects.filter(category__in=categories)
        
        if not cat_questions.exists():
            self.stdout.write('  No Categorize questions found')
            return
        
        # Create a dataframe for Categorize questions
        data = []
        for q in cat_questions:
            # Convert categories and items from JSON to string
            categories_str = json.dumps(q.categories)
            items_str = json.dumps(q.items)
            
            # Get source info
            main_topic_name = q.main_topic.title if q.main_topic else None
            sub_topic_name = q.sub_topic.title if q.sub_topic else None
            topic_name = q.topic.title if q.topic else None
            chapter_name = q.chapter.title if q.chapter else None
            
            # Convert timezone-aware dates to naive
            created_at = self.convert_timezone_aware_dates(q.created_at)
            updated_at = self.convert_timezone_aware_dates(q.updated_at)
            
            # Add to data
            data.append({
                'id': q.id,
                'category_id': q.category_id,
                'category_name': q.category.name,
                'question_text': q.question_text,
                'categories': categories_str,
                'items': items_str,
                'difficulty': q.difficulty,
                'is_active': q.is_active,
                'main_topic_id': q.main_topic_id,
                'main_topic_name': main_topic_name,
                'sub_topic_id': q.sub_topic_id,
                'sub_topic_name': sub_topic_name,
                'topic_id': q.topic_id,
                'topic_name': topic_name,
                'chapter_id': q.chapter_id,
                'chapter_name': chapter_name,
                'created_at': created_at,
                'updated_at': updated_at
            })
        
        # Create dataframe and export to Excel
        df = pd.DataFrame(data)
        df.to_excel(writer, sheet_name='Categorize Questions', index=False)
        self.stdout.write(f'  Exported {len(data)} Categorize questions')

    def export_scramble_questions(self, writer, categories):
        """Export Word Unscramble Questions"""
        self.stdout.write('Exporting Word Unscramble questions...')
        
        # Get Scramble questions for the specified categories
        scramble_questions = WordUnscrambleQuestion.objects.filter(category__in=categories)
        
        if not scramble_questions.exists():
            self.stdout.write('  No Word Unscramble questions found')
            return
        
        # Create a dataframe for Scramble questions
        data = []
        for q in scramble_questions:
            # Get source info
            main_topic_name = q.main_topic.title if q.main_topic else None
            sub_topic_name = q.sub_topic.title if q.sub_topic else None
            topic_name = q.topic.title if q.topic else None
            chapter_name = q.chapter.title if q.chapter else None
            
            # Convert timezone-aware dates to naive
            created_at = self.convert_timezone_aware_dates(q.created_at)
            updated_at = self.convert_timezone_aware_dates(q.updated_at)
            
            # Add to data
            data.append({
                'id': q.id,
                'category_id': q.category_id,
                'category_name': q.category.name,
                'question_text': q.question_text,
                'scrambled_word': q.scrambled_word,
                'correct_word': q.correct_word,
                'hint': q.hint,
                'difficulty': q.difficulty,
                'is_active': q.is_active,
                'main_topic_id': q.main_topic_id,
                'main_topic_name': main_topic_name,
                'sub_topic_id': q.sub_topic_id,
                'sub_topic_name': sub_topic_name,
                'topic_id': q.topic_id,
                'topic_name': topic_name,
                'chapter_id': q.chapter_id,
                'chapter_name': chapter_name,
                'created_at': created_at,
                'updated_at': updated_at
            })
        
        # Create dataframe and export to Excel
        df = pd.DataFrame(data)
        df.to_excel(writer, sheet_name='Scramble Questions', index=False)
        self.stdout.write(f'  Exported {len(data)} Word Unscramble questions')

    def export_categories_summary(self, writer, categories):
        """Export a summary of categories and question counts"""
        self.stdout.write('Creating categories summary...')
        
        # Create a dataframe for category summary
        data = []
        for cat in categories:
            # Count questions in each category
            mcq_count = MCQQuestion.objects.filter(category=cat).count()
            fill_count = FillBlankQuestion.objects.filter(category=cat).count()
            match_count = MatchPairsQuestion.objects.filter(category=cat).count()
            tf_count = TrueFalseQuestion.objects.filter(category=cat).count()
            odd_count = OddOneOutQuestion.objects.filter(category=cat).count()
            cat_count = CategorizeQuestion.objects.filter(category=cat).count()
            scramble_count = WordUnscrambleQuestion.objects.filter(category=cat).count()
            total_count = mcq_count + fill_count + match_count + tf_count + odd_count + cat_count + scramble_count
            
            # Add to data
            data.append({
                'id': cat.id,
                'name': cat.name,
                'description': cat.description,
                'mcq_count': mcq_count,
                'fill_count': fill_count,
                'match_count': match_count,
                'tf_count': tf_count,
                'odd_count': odd_count,
                'cat_count': cat_count,
                'scramble_count': scramble_count,
                'total_count': total_count
            })
        
        # Create dataframe and export to Excel
        df = pd.DataFrame(data)
        df.to_excel(writer, sheet_name='Categories Summary', index=False)
        self.stdout.write(f'  Created summary for {len(data)} categories') 