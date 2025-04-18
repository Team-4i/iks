from django.core.management.base import BaseCommand
from hang.models import (
    QuestionCategory, MCQQuestion, FillBlankQuestion,
    MatchPairsQuestion, TrueFalseQuestion, OddOneOutQuestion,
    CategorizeQuestion, WordUnscrambleQuestion
)

class Command(BaseCommand):
    help = 'Loads test questions for the Hangman game'

    def handle(self, *args, **kwargs):
        # Create categories
        categories = {
            'general': QuestionCategory.objects.create(
                name='General Knowledge',
                description='Basic general knowledge questions'
            ),
            'science': QuestionCategory.objects.create(
                name='Science',
                description='Scientific concepts and facts'
            ),
            'language': QuestionCategory.objects.create(
                name='Language',
                description='Vocabulary and language-related questions'
            )
        }

        # MCQ Questions
        mcq_questions = [
            {
                'category': categories['general'],
                'question_text': 'What is the capital of France?',
                'options': ['Berlin', 'Madrid', 'Paris', 'Rome'],
                'correct_answer': 'Paris',
                'difficulty': 1
            },
            {
                'category': categories['science'],
                'question_text': 'Which planet is known as the Red Planet?',
                'options': ['Earth', 'Mars', 'Jupiter', 'Venus'],
                'correct_answer': 'Mars',
                'difficulty': 1
            }
        ]

        # Fill in the Blank Questions
        fill_blank_questions = [
            {
                'category': categories['language'],
                'question_text': 'Complete the word: Programming Language',
                'answer': 'Python',
                'hint_pattern': 'P_th_n',
                'difficulty': 1
            },
            {
                'category': categories['science'],
                'question_text': 'The process of plants making their own food is called:',
                'answer': 'Photosynthesis',
                'hint_pattern': 'Ph_t_s_nth_s_s',
                'difficulty': 2
            }
        ]

        # Match Pairs Questions
        match_pairs_questions = [
            {
                'category': categories['science'],
                'question_text': 'Match the element with its symbol',
                'pairs': {
                    'Oxygen': 'O',
                    'Hydrogen': 'H',
                    'Carbon': 'C',
                    'Nitrogen': 'N'
                },
                'difficulty': 2
            }
        ]

        # True/False Questions
        true_false_questions = [
            {
                'category': categories['general'],
                'question_text': 'The Great Wall of China is visible from space.',
                'correct_answer': False,
                'difficulty': 1
            },
            {
                'category': categories['science'],
                'question_text': 'Water boils at 100 degrees Celsius at sea level.',
                'correct_answer': True,
                'difficulty': 1
            }
        ]

        # Odd One Out Questions
        odd_one_out_questions = [
            {
                'category': categories['general'],
                'question_text': 'Which is the odd one out?',
                'options': ['Apple', 'Banana', 'Carrot', 'Orange'],
                'correct_answer': 'Carrot',
                'explanation': 'Carrot is a vegetable, while others are fruits',
                'difficulty': 2
            }
        ]

        # Categorize Questions
        categorize_questions = [
            {
                'category': categories['science'],
                'question_text': 'Categorize these animals into their classes',
                'categories': ['Mammals', 'Birds'],
                'items': {
                    'Lion': 'Mammals',
                    'Eagle': 'Birds',
                    'Dolphin': 'Mammals',
                    'Penguin': 'Birds'
                },
                'difficulty': 2
            }
        ]

        # Word Unscramble Questions
        word_unscramble_questions = [
            {
                'category': categories['language'],
                'question_text': 'Unscramble this word: A four-legged furry pet',
                'scrambled_word': 'OGD',
                'correct_word': 'DOG',
                'hint': 'Mans best friend',
                'difficulty': 1
            }
        ]

        # Create all questions
        for q in mcq_questions:
            MCQQuestion.objects.create(
                category=q['category'],
                question_text=q['question_text'],
                options=q['options'],
                correct_answer=q['correct_answer'],
                difficulty=q['difficulty'],
                question_type='MCQ'
            )

        for q in fill_blank_questions:
            FillBlankQuestion.objects.create(
                category=q['category'],
                question_text=q['question_text'],
                answer=q['answer'],
                hint_pattern=q['hint_pattern'],
                difficulty=q['difficulty'],
                question_type='FILL'
            )

        for q in match_pairs_questions:
            MatchPairsQuestion.objects.create(
                category=q['category'],
                question_text=q['question_text'],
                pairs=q['pairs'],
                difficulty=q['difficulty'],
                question_type='MATCH'
            )

        for q in true_false_questions:
            TrueFalseQuestion.objects.create(
                category=q['category'],
                question_text=q['question_text'],
                correct_answer=q['correct_answer'],
                difficulty=q['difficulty'],
                question_type='TF'
            )

        for q in odd_one_out_questions:
            OddOneOutQuestion.objects.create(
                category=q['category'],
                question_text=q['question_text'],
                options=q['options'],
                correct_answer=q['correct_answer'],
                explanation=q['explanation'],
                difficulty=q['difficulty'],
                question_type='ODD'
            )

        for q in categorize_questions:
            CategorizeQuestion.objects.create(
                category=q['category'],
                question_text=q['question_text'],
                categories=q['categories'],
                items=q['items'],
                difficulty=q['difficulty'],
                question_type='CAT'
            )

        for q in word_unscramble_questions:
            WordUnscrambleQuestion.objects.create(
                category=q['category'],
                question_text=q['question_text'],
                scrambled_word=q['scrambled_word'],
                correct_word=q['correct_word'],
                hint=q['hint'],
                difficulty=q['difficulty'],
                question_type='SCRAMBLE'
            )

        self.stdout.write(self.style.SUCCESS('Successfully loaded test questions')) 