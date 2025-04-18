from django.core.management.base import BaseCommand
import random
import time
import google.generativeai as genai
from snake_ladder.models import Cell, CellContent
from dynamicDB.models import SummaryTopic, MainTopic
import json
from django.conf import settings

class Command(BaseCommand):
    help = 'Populates cells with educational content from a summary topic and its main topics'

    def add_arguments(self, parser):
        parser.add_argument('summary_id', type=int, help='ID of the summary topic to use for content')

    def __init__(self):
        super().__init__()
        self.setup_ai()
        
    def setup_ai(self):
        """Set up Google AI if API key is available"""
        api_key = settings.GOOGLE_API_KEY
        
        if api_key:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-pro')
            self.ai_available = True
        else:
            self.stdout.write(self.style.WARNING('No Google API key found. AI content generation disabled.'))
            self.ai_available = False

    def get_summary_topic_data(self, summary_id):
        """Fetch a summary topic and its associated main topics"""
        try:
            # Get the summary topic
            summary_topic = SummaryTopic.objects.get(pk=summary_id)
            
            # Get all main topics associated with this summary topic
            main_topics = summary_topic.main_topics.all().order_by('id')
            
            if not main_topics.exists():
                self.stdout.write(self.style.WARNING(f'No main topics found for summary topic {summary_id}'))
                return None, None
            
            # Format topic data for AI processing
            topic_data = {
                'summary_topic': {
                    'title': summary_topic.title,
                    'description': summary_topic.description,
                    'summary': summary_topic.summary
                },
                'main_topics': []
            }
            
            # Add each main topic with its chapters
            for main_topic in main_topics:
                topic_info = {
                    'id': main_topic.id,
                    'title': main_topic.title,
                    'summary': main_topic.summary,
                    'chapters': []
                }
                
                # Get chapters for this main topic
                chapters = main_topic.chapters.all().order_by('order')
                for chapter in chapters:
                    topic_info['chapters'].append({
                        'title': chapter.title,
                        'content': chapter.content[:1000]  # Limit content length for prompt
                    })
                
                topic_data['main_topics'].append(topic_info)
            
            return summary_topic, topic_data
            
        except SummaryTopic.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Summary topic with ID {summary_id} not found'))
            return None, None
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error fetching summary topic data: {str(e)}'))
            return None, None

    def generate_content_variations(self, topic_data):
        """Generate exactly 80 content variations for normal cells based on topic data"""
        if not topic_data or not self.ai_available:
            return self.generate_basic_content(topic_data)

        summary_topic_info = topic_data['summary_topic']
        main_topics_info = topic_data['main_topics']
        
        # Construct a concise version of the data for the prompt
        summary_title = summary_topic_info['title']
        summary_desc = summary_topic_info['description']
        
        # Create a condensed representation of main topics
        main_topics_text = []
        for topic in main_topics_info:
            topic_text = f"Main Topic: {topic['title']}\n"
            topic_text += f"Summary: {topic['summary']}\n"
            
            # Add a sample of chapters (up to 3)
            sample_chapters = topic['chapters'][:3]
            for chapter in sample_chapters:
                topic_text += f"- Chapter: {chapter['title']}\n"
                # Include a short excerpt from each chapter
                if chapter['content']:
                    excerpt = chapter['content'][:200] + "..." if len(chapter['content']) > 200 else chapter['content']
                    topic_text += f"  Excerpt: {excerpt}\n"
            
            main_topics_text.append(topic_text)
        
        # Join all main topics with separators
        all_topics_text = "\n---\n".join(main_topics_text)

        prompt = f"""
        Based on this summary topic and its main topics:
        
        SUMMARY TOPIC: {summary_title}
        DESCRIPTION: {summary_desc}
        
        MAIN TOPICS:
        {all_topics_text}
        
        Generate educational content in exactly this JSON format:
        {{
            "content": [
                {{
                    "content": "Did you know? [Insert interesting fact about a concept from these topics]",
                    "topic": "[Related topic name]",
                    "source_id": "[ID of a main topic this relates to]"
                }},
                {{
                    "content": "[Topic name]: [2-3 sentences explaining a concept from these topics]",
                    "topic": "[Related topic name]",
                    "source_id": "[ID of a main topic this relates to]"
                }}
            ]
        }}
        
        Rules:
        1. Generate exactly 80 items (for 80 normal cells)
        2. Alternate between "Did you know?" facts and concept explanations
        3. Each content must be based on the provided topics
        4. Keep "Did you know?" facts concise (15-20 words)
        5. Make concept explanations 2-3 sentences long
        6. Ensure all content is unique
        7. Use proper JSON format with double quotes
        8. For source_id, use one of these main topic IDs: {', '.join([str(topic['id']) for topic in main_topics_info])}
        """

        try:
            response = self.model.generate_content(prompt)
            response_text = response.text
            
            # Check if response contains JSON code block
            if "```json" in response_text:
                # Extract the JSON block
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                json_str = response_text[json_start:json_end].strip()
                content_data = json.loads(json_str)
            else:
                # Try to parse the whole response as JSON
                content_data = json.loads(response_text)
            
            return content_data.get('content', [])
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error generating content: {str(e)}'))
            return self.generate_basic_content(topic_data)

    def generate_basic_content(self, topic_data):
        """Generate basic content without AI when API is unavailable or fails"""
        self.stdout.write(self.style.WARNING('Falling back to basic content generation...'))
        content_variations = []
        
        if not topic_data:
            return content_variations
            
        # Get data from main topics
        main_topics = topic_data['main_topics']
        
        # Create fact templates
        fact_templates = [
            "Did you know? {topic} is an important concept in {main_topic}.",
            "Did you know? {topic} relates to {chapter_title}.",
            "Did you know? {topic} contains information about {main_topic}.",
            "Did you know? {main_topic} includes {topic} as a key concept.",
            "Did you know? {chapter_title} is part of {main_topic}."
        ]
        
        # Create explanation templates
        explanation_templates = [
            "{topic}: This concept is central to {main_topic}. It covers {chapter_title} and related ideas.",
            "{topic}: An important aspect of {main_topic}. It explains how {chapter_title} works.",
            "{topic}: In {main_topic}, this represents a key principle. It includes details about {chapter_title}.",
            "{main_topic}: This topic includes {topic} as a core concept. It's related to {chapter_title}.",
            "{chapter_title}: This chapter from {main_topic} explains important details about {topic}."
        ]
        
        # Generate content by cycling through main topics and their chapters
        content_count = 0
        is_fact = True  # Toggle between facts and explanations
        
        # Keep generating until we have 80 items
        while content_count < 80:
            for main_topic in main_topics:
                main_topic_id = main_topic['id']
                main_topic_title = main_topic['title']
                
                for chapter in main_topic.get('chapters', []):
                    chapter_title = chapter['title']
                    
                    # Choose template based on current type
                    if is_fact:
                        template = random.choice(fact_templates)
                        content = template.format(
                            topic=chapter_title, 
                            main_topic=main_topic_title,
                            chapter_title=chapter_title
                        )
                    else:
                        template = random.choice(explanation_templates)
                        content = template.format(
                            topic=chapter_title, 
                            main_topic=main_topic_title,
                            chapter_title=chapter_title
                        )
                    
                    # Add to content variations
                    content_variations.append({
                        'content': content,
                        'topic': main_topic_title,
                        'source_id': main_topic_id
                    })
                    
                    content_count += 1
                    is_fact = not is_fact  # Toggle for next item
                    
                    if content_count >= 80:
                        break
                
                if content_count >= 80:
                    break
        
        return content_variations

    def clear_existing_content(self):
        """Clear any existing cell content"""
        Cell.objects.all().delete()
        # Note: This will also delete CellContent due to cascade delete
        self.stdout.write(self.style.WARNING('Cleared all existing cells and content'))

    def handle(self, *args, **options):
        summary_id = options['summary_id']
        self.stdout.write(f'Fetching summary topic with ID {summary_id}...')
        
        summary_topic, topic_data = self.get_summary_topic_data(summary_id)
        
        if not summary_topic or not topic_data:
            self.stdout.write(self.style.ERROR('Could not fetch summary topic data. Aborting.'))
            return

        self.stdout.write(f'Using summary topic: {summary_topic.title}')
        self.stdout.write(f'Contains {len(topic_data["main_topics"])} main topics')
        
        self.stdout.write('Generating content variations...')
        content_variations = self.generate_content_variations(topic_data)
        
        if not content_variations:
            self.stdout.write(self.style.ERROR('No content generated. Aborting.'))
            return

        if len(content_variations) < 80:
            self.stdout.write(self.style.ERROR(f'Not enough content generated. Need 80, got {len(content_variations)}'))
            # Duplicate existing content to reach 80 items
            original_count = len(content_variations)
            while len(content_variations) < 80:
                index = (len(content_variations) - original_count) % original_count
                content_variations.append(content_variations[index])
            self.stdout.write(self.style.WARNING(f'Duplicated content to reach 80 items'))

        # Clear existing cells and content
        self.clear_existing_content()

        # Create all cells first (1-100)
        self.stdout.write('Creating all cells...')
        for number in range(1, 101):
            Cell.objects.create(number=number)

        # Create CellContent objects and map to normal cells
        self.stdout.write('Creating and mapping content...')
        normal_cell_count = 0
        content_index = 0

        for number in range(1, 101):
            cell = Cell.objects.get(number=number)
            
            if not Cell.is_snake_ladder_cell(number):
                # Create content for normal cell
                content_data = content_variations[content_index]
                
                # Extract source_id if available
                source_id = content_data.get('source_id', None)
                
                # Create cell content
                cell_content = CellContent.objects.create(
                    content=content_data['content'],
                    topic=content_data['topic'],
                    source_id=source_id  # Store source main topic ID
                )
                
                # Add to cell's contents and set as current
                cell.contents.add(cell_content)
                cell.current_content = cell_content
                cell.save()
                
                normal_cell_count += 1
                content_index += 1

        # Verify counts
        normal_cells = Cell.objects.filter(cell_type='NORMAL').count()
        snake_ladder_cells = Cell.objects.filter(cell_type='SNAKE_LADDER').count()
        content_count = CellContent.objects.count()

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully populated cells:\n'
                f'- Normal cells: {normal_cells} (should be 80)\n'
                f'- Snake/Ladder cells: {snake_ladder_cells} (should be 20)\n'
                f'- Content pieces created: {content_count} (should be 80)\n'
                f'All normal cells have content from summary topic: {summary_topic.title}'
            )
        )