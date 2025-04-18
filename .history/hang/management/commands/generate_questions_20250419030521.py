import os
import google.generativeai as genai
import json
import random
import time
from django.core.management.base import BaseCommand
from django.conf import settings
from dynamicDB.models import SubTopic, MainTopic, Topic, Chapter
from hang.models import (
    QuestionCategory, MCQQuestion, FillBlankQuestion, 
    MatchPairsQuestion, TrueFalseQuestion, OddOneOutQuestion,
    CategorizeQuestion, WordUnscrambleQuestion
)

# Configure the Gemini API with multiple API keys for rotation
API_KEYS = [
    'AIzaSyA8DaPlDtUTyzwjo8M6aOwFcfGDLU7itJg',  # Original key
    'AIzaSyAyC6TYEiuv3gS4uXnwfyFkPjrWsz8hzjE',  # Additional key 1
    'AIzaSyAo7CfxZxTHw-6mh6UHAjhTQdNGWcLgKnY',  # Additional key 2
    'AIzaSyDuG7f9pPhSJA9c0OffTWAp_5LNPJ-tS48',  # Additional key 3
]
current_key_index = 0

def get_next_api_key():
    global current_key_index
    key = API_KEYS[current_key_index]
    # Rotate to the next key
    current_key_index = (current_key_index + 1) % len(API_KEYS)
    return key

# Initial configuration with the first key
genai.configure(api_key=get_next_api_key())

# Define base model
def get_model():
    # Configure with a potentially new key each time
    genai.configure(api_key=get_next_api_key())
    return genai.GenerativeModel('gemini-1.5-pro')

class Command(BaseCommand):
    help = 'Generate hangman game questions using Gemini AI based on document content'

    def add_arguments(self, parser):
        parser.add_argument(
            '--subtopic_id',
            type=int,
            help='ID of the specific subtopic to generate questions for',
            required=False
        )
        parser.add_argument(
            '--limit',
            type=int,
            help='Limit the number of subtopics to process',
            required=False
        )
        parser.add_argument(
            '--force_regenerate',
            action='store_true',
            help='Force regeneration of questions even if they exist',
            required=False
        )
        parser.add_argument(
            '--sleep',
            type=int,
            default=5,
            help='Sleep time between API calls in seconds',
            required=False
        )

    def handle(self, *args, **options):
        subtopic_id = options.get('subtopic_id')
        limit = options.get('limit')
        force_regenerate = options.get('force_regenerate', False)
        self.sleep_time = options.get('sleep', 5)
        
        # Query subtopics based on arguments
        if subtopic_id:
            subtopics = SubTopic.objects.filter(id=subtopic_id)
            self.stdout.write(self.style.SUCCESS(f'Generating questions for specific subtopic ID: {subtopic_id}'))
        else:
            subtopics = SubTopic.objects.all()
            if limit:
                subtopics = subtopics[:limit]
                self.stdout.write(self.style.SUCCESS(f'Processing limited set of {limit} subtopics'))
            else:
                self.stdout.write(self.style.SUCCESS(f'Processing all {subtopics.count()} subtopics'))
        
        # Process each subtopic
        for subtopic in subtopics:
            self.generate_questions_for_subtopic(subtopic, force_regenerate)
            # Sleep between subtopics to avoid rate limits
            self.stdout.write(f"Sleeping for {self.sleep_time*2} seconds between subtopics...")
            time.sleep(self.sleep_time * 2)
    
    def generate_questions_for_subtopic(self, subtopic, force_regenerate):
        """Generate questions for a specific subtopic"""
        self.stdout.write(self.style.SUCCESS(f'Processing subtopic: {subtopic.title}'))
        
        # Get the content to be used for question generation
        content = self.collect_content_for_subtopic(subtopic)
        
        # Get related topics and chapter information
        main_topic = subtopic.topic_group
        topics = subtopic.main_topics.all()
        
        # Check if questions already exist for this subtopic
        category_name = f"ST_{subtopic.id}_{subtopic.title[:30]}"
        category, created = QuestionCategory.objects.get_or_create(
            name=category_name,
            defaults={'description': f"Questions for subtopic: {subtopic.title}"}
        )
        
        if not force_regenerate:
            # Count questions for this category
            mcq_count = MCQQuestion.objects.filter(category=category).count()
            fill_count = FillBlankQuestion.objects.filter(category=category).count()
            match_count = MatchPairsQuestion.objects.filter(category=category).count()
            tf_count = TrueFalseQuestion.objects.filter(category=category).count()
            odd_count = OddOneOutQuestion.objects.filter(category=category).count()
            cat_count = CategorizeQuestion.objects.filter(category=category).count()
            scramble_count = WordUnscrambleQuestion.objects.filter(category=category).count()
            
            total_count = mcq_count + fill_count + match_count + tf_count + odd_count + cat_count + scramble_count
            
            if total_count >= 70:
                self.stdout.write(self.style.WARNING(
                    f'Skipping {subtopic.title}: Already has {total_count} questions'
                ))
                return
        
        # Generate questions for each type
        self.generate_mcq_questions(subtopic, main_topic, topics, category, content)
        time.sleep(self.sleep_time)  # Sleep between question types
        
        self.generate_fill_questions(subtopic, main_topic, topics, category, content)
        time.sleep(self.sleep_time)  # Sleep between question types
        
        self.generate_match_questions(subtopic, main_topic, topics, category, content)
        time.sleep(self.sleep_time)  # Sleep between question types
        
        self.generate_tf_questions(subtopic, main_topic, topics, category, content)
        time.sleep(self.sleep_time)  # Sleep between question types
        
        self.generate_odd_questions(subtopic, main_topic, topics, category, content)
        time.sleep(self.sleep_time)  # Sleep between question types
        
        self.generate_cat_questions(subtopic, main_topic, topics, category, content)
        time.sleep(self.sleep_time)  # Sleep between question types
        
        self.generate_scramble_questions(subtopic, main_topic, topics, category, content)
        
        self.stdout.write(self.style.SUCCESS(f'Completed generating questions for: {subtopic.title}'))
    
    def collect_content_for_subtopic(self, subtopic):
        """Collect content from topics and chapters related to this subtopic"""
        content = f"SUBTOPIC: {subtopic.title}\n{subtopic.description}\n\n"
        
        # Get main topic info
        main_topic = subtopic.topic_group
        content += f"MAIN_TOPIC: {main_topic.title}\n{main_topic.description}\n\n"
        
        # Get related topics
        for topic in subtopic.main_topics.all():
            content += f"TOPIC: {topic.title}\n{topic.summary}\n\n"
            
            # Get related chapters for this topic
            for chapter in topic.chapters.all():
                content += f"CHAPTER: {chapter.title}\n{chapter.content}\n\n"
        
        return content
    
    def generate_mcq_questions(self, subtopic, main_topic, topics, category, content):
        """Generate 10 Multiple Choice Questions"""
        self.stdout.write('Generating MCQ questions...')
        
        # Prepare the prompt for Gemini
        prompt = f"""
        Based on the following content, create 10 multiple-choice questions.
        
        CONTENT:
        {content[:8000]}  # Limit content to avoid exceeding token limits
        
        Return these questions in the following JSON format:
        
        [
            {{
                "question_text": "Question 1?",
                "options": ["Option A", "Option B", "Option C", "Option D"],
                "correct_answer": "Option A",
                "difficulty": 2
            }},
            ...and so on for all 10 questions
        ]
        
        Guidelines:
        - Create diverse questions covering different aspects of the content
        - Ensure the correct answer is one of the options
        - Set difficulty level (1: Easy, 2: Medium, 3: Hard)
        - Make sure all options are plausible
        - Include exactly 4 options per question
        
        Return valid JSON only, without any other text.
        """
        
        max_retries = 2
        retries = 0
        
        while retries <= max_retries:
            try:
                # Get a fresh model with potentially new API key
                model = get_model()
                
                # Generate questions using Gemini
                response = model.generate_content(prompt)
                response_text = response.text
                
                # Extract JSON from response
                try:
                    # Find JSON within the response if it's wrapped in markdown or other text
                    start_idx = response_text.find('[')
                    end_idx = response_text.rfind(']') + 1
                    
                    if start_idx != -1 and end_idx != -1:
                        json_str = response_text[start_idx:end_idx]
                        questions = json.loads(json_str)
                    else:
                        questions = json.loads(response_text)
                    
                    # Process the generated questions
                    for i, q_data in enumerate(questions[:10]):  # Ensure we only take 10
                        try:
                            # Find a related chapter if possible
                            chapter = None
                            if topics.exists():
                                # Get a random topic
                                topic = random.choice(list(topics))
                                # Get a random chapter from that topic if it has any
                                chapters = topic.chapters.all()
                                if chapters.exists():
                                    chapter = random.choice(list(chapters))
                            
                            # Create the MCQ question with source info
                            question = MCQQuestion(
                                category=category,
                                question_type='MCQ',
                                question_text=q_data['question_text'],
                                difficulty=q_data.get('difficulty', 2),
                                options=q_data['options'],
                                correct_answer=q_data['correct_answer'],
                                is_active=True,
                                # Add source tracking
                                main_topic=main_topic,
                                sub_topic=subtopic,
                                topic=topic if topics.exists() else None,
                                chapter=chapter
                            )
                            question.save()
                            self.stdout.write(f'  - Created MCQ question {i+1}: {q_data["question_text"][:30]}...')
                        except Exception as e:
                            self.stdout.write(self.style.ERROR(f'  - Error saving MCQ question {i+1}: {str(e)}'))
                    
                    # If we got here, we succeeded
                    break
                    
                except json.JSONDecodeError:
                    self.stdout.write(self.style.ERROR(f'Invalid JSON response for MCQ questions'))
                    if retries < max_retries:
                        retries += 1
                        self.stdout.write(f"Retrying ({retries}/{max_retries})...")
                        time.sleep(self.sleep_time)
                    else:
                        self.stdout.write(self.style.ERROR(response_text))
                        break
                        
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error generating MCQ questions: {str(e)}'))
                if "429" in str(e) and retries < max_retries:
                    # Rate limit error, retry with a new key after sleeping
                    retries += 1
                    self.stdout.write(f"Rate limit hit. Retrying with a new API key ({retries}/{max_retries})...")
                    # Additional sleep for rate limit
                    time.sleep(self.sleep_time * 3)
                else:
                    break
    
    def generate_fill_questions(self, subtopic, main_topic, topics, category, content):
        """Generate 10 Fill in the Blank Questions"""
        self.stdout.write('Generating Fill in the Blank questions...')
        
        prompt = f"""
        Based on the following content, create 10 fill-in-the-blank questions.
        
        CONTENT:
        {content[:8000]}
        
        Return these questions in the following JSON format:
        
        [
            {{
                "question_text": "Complete this sentence: The process of ___ is essential for DNA replication.",
                "answer": "mitosis",
                "hint_pattern": "m_t_s_s",
                "difficulty": 2
            }},
            ...and so on for all 10 questions
        ]
        
        Guidelines:
        - Create diverse questions covering different aspects of the content
        - Make the blank represent an important concept from the content
        - Provide a hint pattern where underscores replace some letters
        - Set difficulty level (1: Easy, 2: Medium, 3: Hard)
        
        Return valid JSON only, without any other text.
        """
        
        try:
            response = get_model().generate_content(prompt)
            response_text = response.text
            
            try:
                # Extract JSON
                start_idx = response_text.find('[')
                end_idx = response_text.rfind(']') + 1
                
                if start_idx != -1 and end_idx != -1:
                    json_str = response_text[start_idx:end_idx]
                    questions = json.loads(json_str)
                else:
                    questions = json.loads(response_text)
                
                # Process the generated questions
                for i, q_data in enumerate(questions[:10]):
                    try:
                        # Create the Fill in the Blank question
                        question = FillBlankQuestion(
                            category=category,
                            question_type='FILL',
                            question_text=q_data['question_text'],
                            difficulty=q_data.get('difficulty', 2),
                            answer=q_data['answer'],
                            hint_pattern=q_data.get('hint_pattern', ''),
                            is_active=True
                        )
                        question.save()
                        self.stdout.write(f'  - Created Fill question {i+1}: {q_data["question_text"][:30]}...')
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'  - Error saving Fill question {i+1}: {str(e)}'))
            except json.JSONDecodeError:
                self.stdout.write(self.style.ERROR(f'Invalid JSON response for Fill questions'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error generating Fill questions: {str(e)}'))
    
    def generate_match_questions(self, subtopic, main_topic, topics, category, content):
        """Generate 10 Matching Pairs Questions"""
        self.stdout.write('Generating Matching Pairs questions...')
        
        prompt = f"""
        Based on the following content, create 10 matching pairs questions.
        
        CONTENT:
        {content[:8000]}
        
        Return these questions in the following JSON format:
        
        [
            {{
                "question_text": "Match the following terms with their definitions:",
                "pairs": {{"Term 1": "Definition 1", "Term 2": "Definition 2", "Term 3": "Definition 3", "Term 4": "Definition 4"}},
                "difficulty": 2
            }},
            ...and so on for all 10 questions
        ]
        
        Guidelines:
        - Create diverse matching tasks (terms-definitions, concepts-examples, cause-effect)
        - Include at least 4 pairs per question
        - Set difficulty level (1: Easy, 2: Medium, 3: Hard)
        - Ensure pairs are related to important concepts from the content
        
        Return valid JSON only, without any other text.
        """
        
        try:
            response = get_model().generate_content(prompt)
            response_text = response.text
            
            try:
                # Extract JSON
                start_idx = response_text.find('[')
                end_idx = response_text.rfind(']') + 1
                
                if start_idx != -1 and end_idx != -1:
                    json_str = response_text[start_idx:end_idx]
                    questions = json.loads(json_str)
                else:
                    questions = json.loads(response_text)
                
                # Process the generated questions
                for i, q_data in enumerate(questions[:10]):
                    try:
                        # Create the Matching Pairs question
                        question = MatchPairsQuestion(
                            category=category,
                            question_type='MATCH',
                            question_text=q_data['question_text'],
                            difficulty=q_data.get('difficulty', 2),
                            pairs=q_data['pairs'],
                            is_active=True
                        )
                        question.save()
                        self.stdout.write(f'  - Created Match question {i+1}: {q_data["question_text"][:30]}...')
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'  - Error saving Match question {i+1}: {str(e)}'))
            except json.JSONDecodeError:
                self.stdout.write(self.style.ERROR(f'Invalid JSON response for Match questions'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error generating Match questions: {str(e)}'))
    
    def generate_tf_questions(self, subtopic, main_topic, topics, category, content):
        """Generate 10 True/False Questions"""
        self.stdout.write('Generating True/False questions...')
        
        prompt = f"""
        Based on the following content, create 10 true/false questions.
        
        CONTENT:
        {content[:8000]}
        
        Return these questions in the following JSON format:
        
        [
            {{
                "question_text": "The human body has 206 bones.",
                "correct_answer": true,
                "difficulty": 1
            }},
            ...and so on for all 10 questions
        ]
        
        Guidelines:
        - Create diverse questions covering different aspects of the content
        - Include both true and false statements
        - Make false statements plausible but clearly incorrect based on the content
        - Set difficulty level (1: Easy, 2: Medium, 3: Hard)
        
        Return valid JSON only, without any other text.
        """
        
        try:
            response = get_model().generate_content(prompt)
            response_text = response.text
            
            try:
                # Extract JSON
                start_idx = response_text.find('[')
                end_idx = response_text.rfind(']') + 1
                
                if start_idx != -1 and end_idx != -1:
                    json_str = response_text[start_idx:end_idx]
                    questions = json.loads(json_str)
                else:
                    questions = json.loads(response_text)
                
                # Process the generated questions
                for i, q_data in enumerate(questions[:10]):
                    try:
                        # Convert to boolean if it's a string ("true"/"false")
                        if isinstance(q_data['correct_answer'], str):
                            correct_answer = q_data['correct_answer'].lower() == 'true'
                        else:
                            correct_answer = bool(q_data['correct_answer'])
                            
                        # Create the True/False question
                        question = TrueFalseQuestion(
                            category=category,
                            question_type='TF',
                            question_text=q_data['question_text'],
                            difficulty=q_data.get('difficulty', 1),
                            correct_answer=correct_answer,
                            is_active=True
                        )
                        question.save()
                        self.stdout.write(f'  - Created T/F question {i+1}: {q_data["question_text"][:30]}...')
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'  - Error saving T/F question {i+1}: {str(e)}'))
            except json.JSONDecodeError:
                self.stdout.write(self.style.ERROR(f'Invalid JSON response for T/F questions'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error generating T/F questions: {str(e)}'))
    
    def generate_odd_questions(self, subtopic, main_topic, topics, category, content):
        """Generate 10 Odd One Out Questions"""
        self.stdout.write('Generating Odd One Out questions...')
        
        prompt = f"""
        Based on the following content, create 10 'odd one out' questions.
        
        CONTENT:
        {content[:8000]}
        
        Return these questions in the following JSON format:
        
        [
            {{
                "question_text": "Which one of these doesn't belong in the group?",
                "options": ["Item 1", "Item 2", "Item 3", "Item 4"],
                "correct_answer": "Item 3",
                "explanation": "Items 1, 2, and 4 are all related to X, while Item 3 is related to Y.",
                "difficulty": 2
            }},
            ...and so on for all 10 questions
        ]
        
        Guidelines:
        - Create diverse questions covering different aspects of the content
        - Include exactly 4 options per question
        - Provide a clear explanation for why the odd one out is different
        - Set difficulty level (1: Easy, 2: Medium, 3: Hard)
        - Ensure the distinction is based on concepts from the content
        
        Return valid JSON only, without any other text.
        """
        
        try:
            response = get_model().generate_content(prompt)
            response_text = response.text
            
            try:
                # Extract JSON
                start_idx = response_text.find('[')
                end_idx = response_text.rfind(']') + 1
                
                if start_idx != -1 and end_idx != -1:
                    json_str = response_text[start_idx:end_idx]
                    questions = json.loads(json_str)
                else:
                    questions = json.loads(response_text)
                
                # Process the generated questions
                for i, q_data in enumerate(questions[:10]):
                    try:
                        # Create the Odd One Out question
                        question = OddOneOutQuestion(
                            category=category,
                            question_type='ODD',
                            question_text=q_data['question_text'],
                            difficulty=q_data.get('difficulty', 2),
                            options=q_data['options'],
                            correct_answer=q_data['correct_answer'],
                            explanation=q_data['explanation'],
                            is_active=True
                        )
                        question.save()
                        self.stdout.write(f'  - Created Odd One Out question {i+1}: {q_data["question_text"][:30]}...')
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'  - Error saving Odd One Out question {i+1}: {str(e)}'))
            except json.JSONDecodeError:
                self.stdout.write(self.style.ERROR(f'Invalid JSON response for Odd One Out questions'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error generating Odd One Out questions: {str(e)}'))
    
    def generate_cat_questions(self, subtopic, main_topic, topics, category, content):
        """Generate 10 Categorize Questions"""
        self.stdout.write('Generating Categorize questions...')
        
        prompt = f"""
        Based on the following content, create 10 categorization questions.
        
        CONTENT:
        {content[:8000]}
        
        Return these questions in the following JSON format:
        
        [
            {{
                "question_text": "Categorize these terms into their appropriate groups:",
                "categories": ["Category A", "Category B", "Category C"],
                "items": {{"Item 1": "Category A", "Item 2": "Category B", "Item 3": "Category C", "Item 4": "Category A", "Item 5": "Category B", "Item 6": "Category C"}},
                "difficulty": 2
            }},
            ...and so on for all 10 questions
        ]
        
        Guidelines:
        - Create diverse categorization tasks based on the content
        - Include 2-3 categories per question
        - Include at least 6 items to categorize
        - Distribute items evenly across categories
        - Set difficulty level (1: Easy, 2: Medium, 3: Hard)
        - Ensure categories and items are related to important concepts from the content
        
        Return valid JSON only, without any other text.
        """
        
        try:
            response = get_model().generate_content(prompt)
            response_text = response.text
            
            try:
                # Extract JSON
                start_idx = response_text.find('[')
                end_idx = response_text.rfind(']') + 1
                
                if start_idx != -1 and end_idx != -1:
                    json_str = response_text[start_idx:end_idx]
                    questions = json.loads(json_str)
                else:
                    questions = json.loads(response_text)
                
                # Process the generated questions
                for i, q_data in enumerate(questions[:10]):
                    try:
                        # Create the Categorize question
                        question = CategorizeQuestion(
                            category=category,
                            question_type='CAT',
                            question_text=q_data['question_text'],
                            difficulty=q_data.get('difficulty', 2),
                            categories=q_data['categories'],
                            items=q_data['items'],
                            is_active=True
                        )
                        question.save()
                        self.stdout.write(f'  - Created Categorize question {i+1}: {q_data["question_text"][:30]}...')
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'  - Error saving Categorize question {i+1}: {str(e)}'))
            except json.JSONDecodeError:
                self.stdout.write(self.style.ERROR(f'Invalid JSON response for Categorize questions'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error generating Categorize questions: {str(e)}'))
    
    def generate_scramble_questions(self, subtopic, main_topic, topics, category, content):
        """Generate 10 Word Unscramble Questions"""
        self.stdout.write('Generating Word Unscramble questions...')
        
        prompt = f"""
        Based on the following content, create 10 word unscramble questions.
        
        CONTENT:
        {content[:8000]}
        
        Return these questions in the following JSON format:
        
        [
            {{
                "question_text": "Unscramble this term related to the content:",
                "scrambled_word": "OLGIOBY",
                "correct_word": "BIOLOGY",
                "hint": "The study of living organisms",
                "difficulty": 2
            }},
            ...and so on for all 10 questions
        ]
        
        Guidelines:
        - Choose important terms or concepts from the content
        - Scramble the letters in a way that makes it challenging but solvable
        - Provide a helpful hint that describes the term
        - Set difficulty level (1: Easy, 2: Medium, 3: Hard)
        - Ensure the scrambled word is different from the correct word
        - Select words that are at least 5 letters long
        
        Return valid JSON only, without any other text.
        """
        
        try:
            response = get_model().generate_content(prompt)
            response_text = response.text
            
            try:
                # Extract JSON
                start_idx = response_text.find('[')
                end_idx = response_text.rfind(']') + 1
                
                if start_idx != -1 and end_idx != -1:
                    json_str = response_text[start_idx:end_idx]
                    questions = json.loads(json_str)
                else:
                    questions = json.loads(response_text)
                
                # Process the generated questions
                for i, q_data in enumerate(questions[:10]):
                    try:
                        # Create the Word Unscramble question
                        question = WordUnscrambleQuestion(
                            category=category,
                            question_type='SCRAMBLE',
                            question_text=q_data['question_text'],
                            difficulty=q_data.get('difficulty', 2),
                            scrambled_word=q_data['scrambled_word'],
                            correct_word=q_data['correct_word'],
                            hint=q_data.get('hint', ''),
                            is_active=True
                        )
                        question.save()
                        self.stdout.write(f'  - Created Word Unscramble question {i+1}: {q_data["scrambled_word"]} -> {q_data["correct_word"]}')
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'  - Error saving Word Unscramble question {i+1}: {str(e)}'))
            except json.JSONDecodeError:
                self.stdout.write(self.style.ERROR(f'Invalid JSON response for Word Unscramble questions'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error generating Word Unscramble questions: {str(e)}')) 