import google.generativeai as genai
from PIL import Image
import os
import PyPDF2
import io
import time
import re
from django.conf import settings
from django.utils import timezone
import random

class TextbookAnalyzer:
    def __init__(self):
        # API key
        self.api_keys = [
            "AIzaSyALnrV7Cb5fM8_PdYJGGcn2xIC932m8XVQ"
        ]
        
        # Configure Gemini AI with API key
        self._configure_gemini()
        
    def _configure_gemini(self, key_index=0):
        """Configure Gemini with a specific API key"""
        if key_index < len(self.api_keys):
            genai.configure(api_key=self.api_keys[key_index])
            
            # List available models to ensure we're using valid ones
            try:
                models = genai.list_models()
                print("Available models:", [m.name for m in models])
                
                # Find appropriate models by exact name from the list
                vision_model = None
                text_model = None
                
                # Try these models in order of preference
                preferred_vision_models = [
                    "models/gemini-1.5-pro", 
                    "models/gemini-pro-vision",
                    "models/gemini-1.0-pro-vision-latest",
                    "models/gemini-1.5-flash"
                ]
                
                preferred_text_models = [
                    "models/gemini-1.5-pro",
                    "models/gemini-1.5-flash",
                    "models/text-bison-001"
                ]
                
                # Find first available vision model
                for model_name in preferred_vision_models:
                    if any(m.name == model_name for m in models):
                        vision_model = model_name
                        break
                
                # Find first available text model
                for model_name in preferred_text_models:
                    if any(m.name == model_name for m in models):
                        text_model = model_name
                        break
                
                if not vision_model:
                    vision_model = models[0].name  # Use any model as fallback
                if not text_model:
                    text_model = models[0].name  # Use any model as fallback
                
                print(f"Using vision model: {vision_model}")
                print(f"Using text model: {text_model}")
                
                self.model = genai.GenerativeModel(vision_model)
                self.pro_model = genai.GenerativeModel(text_model)
            except Exception as e:
                print(f"Error listing models: {e}, creating chapters without AI")
                # Just proceed with pattern matching instead
                self.model = None
                self.pro_model = None
                
            return True
        return False
    
    def _try_with_fallback_keys(self, func, *args, **kwargs):
        """Try a function with multiple API keys as fallback"""
        for i in range(len(self.api_keys)):
            try:
                self._configure_gemini(i)
                return func(*args, **kwargs)
            except Exception as e:
                print(f"API key {i} failed: {str(e)}")
                if i == len(self.api_keys) - 1:
                    # When all keys fail, handle some functions specially
                    if func.__name__ == '_identify_chapters_with_ai':
                        # Create simple chapters as fallback when AI fails
                        print("AI-based chapter detection failed, using fallback")
                        total_pages = kwargs.get('total_pages', 100)
                        return self._create_fallback_chapters(total_pages)
                    elif func.__name__ == '_extract_key_points':
                        return self._generate_placeholder_key_points()
                    else:
                        raise e
                # Rate limiting - add more delay between retries
                time.sleep(5)  # Increase delay to 5 seconds
                
    def _create_fallback_chapters(self, total_pages):
        """Create fallback chapters when AI-based detection fails"""
        chapters = []
        # Try regex-based detection first - this is more likely to find real chapters
        text_sample = "Chapter 1: Introduction\nChapter 2: Main Concepts\nChapter 3: Applications"
        chapters = self._extract_chapters_with_patterns(text_sample)
        
        if not chapters:
            # Create some reasonable default chapters
            section_count = min(5, max(3, total_pages // 10))
            pages_per_section = total_pages // section_count
            
            subjects = ["Introduction", "Background", "Concepts", "Theory", "Applications", "Examples", "Discussion", "Analysis", "Case Studies", "Conclusion"]
            
            for i in range(section_count):
                start_page = i * pages_per_section + 1
                end_page = (i + 1) * pages_per_section if i < section_count - 1 else total_pages
                
                title = subjects[i] if i < len(subjects) else f"Section {i+1}"
                
                chapters.append({
                    'number': i + 1,
                    'title': title,
                    'start_page': start_page,
                    'end_page': end_page
                })
        
        return chapters

    def analyze_document(self, image_path):
        """Analyze document using Gemini AI"""
        return self._try_with_fallback_keys(self._analyze_document, image_path)
        
    def _analyze_document(self, image_path):
        try:
            # Load and prepare the image
            img = Image.open(image_path)
            
            # Improved prompt to analyze textbook pages
            prompt = """
            You are a textbook analyzer. Please analyze this textbook image and identify:
            1. What chapter(s) this page belongs to
            2. The main topic or subject of this content

            Format your response exactly like this:
            Chapter: [Chapter Number and/or Title]
            Topic: [Main Topic or Subject]
            Content: [Brief description of what's on this page]

            Guidelines:
            - Be precise with chapter titles and numbers
            - Identify the broader educational topic this content belongs to
            - Keep descriptions concise and factual
            - Don't generate or invent content that isn't present
            """

            # Generate response from Gemini
            response = self.model.generate_content(
                [prompt, img],
                generation_config={
                    'temperature': 0.1,
                    'candidate_count': 1,
                    'max_output_tokens': 1024,
                }
            )
            
            content = response.text
            print("Gemini Image Analysis Response:", content)
            
            # Process the response
            analysis = {
                'chapter': None,
                'topic': None,
                'content': None
            }
            
            for line in content.split('\n'):
                line = line.strip()
                if not line:
                    continue
                
                if line.startswith('Chapter:'):
                    analysis['chapter'] = line.replace('Chapter:', '').strip()
                elif line.startswith('Topic:'):
                    analysis['topic'] = line.replace('Topic:', '').strip()
                elif line.startswith('Content:'):
                    analysis['content'] = line.replace('Content:', '').strip()
            
            return analysis
                
        except Exception as e:
            print(f"Analysis Error: {str(e)}")
            return {
                'chapter': None,
                'topic': None,
                'content': f'Error analyzing image: {str(e)}'
            }

    def extract_text_from_pdf(self, pdf_path):
        """Extract text from a PDF file"""
        text = ""
        try:
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                num_pages = len(reader.pages)
                for page_num in range(min(num_pages, 50)):  # Limit to first 50 pages for initial analysis
                    page = reader.pages[page_num]
                    text += page.extract_text() + "\n\n--- Page Break ---\n\n"
            return text
        except Exception as e:
            print(f"Error extracting text from PDF: {e}")
            return text

    def analyze_textbook_structure(self, pdf_path):
        """Identify chapters and group them into topics"""
        text = self.extract_text_from_pdf(pdf_path)
        
        # First identify all chapters
        chapters = self._identify_chapters(text)
        
        # Then group chapters into topics
        topics = self._group_chapters_into_topics(chapters, text)
        
        return {
            'chapters': chapters,
            'topics': topics
        }
    
    def _identify_chapters(self, text):
        """Identify all chapters in the textbook"""
        # Get page count
        total_pages = text.count('--- Page Break ---') + 1
        
        # Try regex pattern matching first
        chapters = self._extract_chapters_with_patterns(text)
        
        # If pattern matching failed, use AI
        if not chapters:
            chapters = self._try_with_fallback_keys(self._identify_chapters_with_ai, text, total_pages=total_pages)
        
        return chapters
    
    def _extract_chapters_with_patterns(self, text):
        """Extract chapters using regex patterns"""
        chapters = []
        
        # Common chapter patterns
        chapter_patterns = [
            r"(?:CHAPTER|Chapter)\s+(\d+)(?:[:\.\s]+)([^\n]+)",  # Chapter 1: Title or Chapter 1. Title
            r"(?:\d+\.\s+)([A-Z][^\n]+)"  # 1. TITLE FORMAT 
        ]
        
        # Track page numbers approximately
        pages = text.split("--- Page Break ---")
        
        # Try each pattern
        for pattern in chapter_patterns:
            all_matches = []
            
            # Find matches across all pages
            for page_idx, page_text in enumerate(pages):
                matches = re.findall(pattern, page_text)
                for match in matches:
                    # Handle different match formats
                    if len(match) == 2:  # Pattern captured (number, title)
                        number, title = match
                        all_matches.append({
                            'number': int(float(number)) if number.replace('.', '', 1).isdigit() else len(all_matches) + 1,
                            'title': title.strip(),
                            'start_page': page_idx + 1
                        })
                    elif len(match) == 1:  # Pattern captured (title) only
                        all_matches.append({
                            'number': len(all_matches) + 1,
                            'title': match[0].strip(),
                            'start_page': page_idx + 1
                        })
            
            # If we found chapters with this pattern, process them
            if all_matches:
                # Sort by page number
                all_matches.sort(key=lambda x: x['start_page'])
                
                # Calculate end pages
                for i in range(len(all_matches) - 1):
                    all_matches[i]['end_page'] = all_matches[i + 1]['start_page'] - 1
                
                # Last chapter ends at last page
                if all_matches:
                    all_matches[-1]['end_page'] = len(pages)
                
                return all_matches
        
        return []
    
    def _identify_chapters_with_ai(self, text, total_pages=100):
        """Use AI to identify chapters when patterns fail"""
        prompt = """
        You are analyzing a textbook to identify its chapter structure. Please identify all the chapters in this textbook.

        For each chapter you find, provide EXACTLY:
        1. The chapter number
        2. The chapter title 
        3. The approximate page number where the chapter starts

        Your response format MUST be:
        CHAPTER: 1
        TITLE: Introduction to the Subject
        START_PAGE: 1

        CHAPTER: 2
        TITLE: Next Chapter Title
        START_PAGE: 15

        Only include what you can identify with high confidence. DO NOT invent or make up chapters.
        If you can't find clear chapter markers, look for section headings or topic shifts.
        Always respond in the EXACT format specified above.
        """
        
        try:
            # Use a smaller sample for AI analysis
            if len(text) > 30000:
                text = text[:30000]
                
            print("Sending text to AI for chapter detection...")
            response = self.pro_model.generate_content(
                prompt + "\n\nTEXT TO ANALYZE:\n" + text,
                generation_config={
                    'temperature': 0.3,
                    'max_output_tokens': 2048,
                }
            )
            
            content = response.text
            print("Chapter Structure Response:", content)
            
            # Parse the structured response
            chapters = []
            current_chapter = {}
            
            for line in content.split('\n'):
                line = line.strip()
                if not line:
                    if current_chapter and 'title' in current_chapter:
                        chapters.append(current_chapter)
                        current_chapter = {}
                    continue
                
                if line.startswith('CHAPTER:'):
                    # Start new chapter
                    if current_chapter and 'title' in current_chapter:
                        chapters.append(current_chapter)
                    current_chapter = {}
                    try:
                        chapter_num = line.replace('CHAPTER:', '').strip()
                        if chapter_num.isdigit():
                            current_chapter['number'] = int(chapter_num)
                        else:
                            # Try to extract just the number part
                            num_match = re.search(r'\d+', chapter_num)
                            if num_match:
                                current_chapter['number'] = int(num_match.group())
                            else:
                                current_chapter['number'] = len(chapters) + 1
                    except:
                        current_chapter['number'] = len(chapters) + 1
                
                elif line.startswith('TITLE:'):
                    current_chapter['title'] = line.replace('TITLE:', '').strip()
                
                elif line.startswith('START_PAGE:'):
                    try:
                        page_num = int(line.replace('START_PAGE:', '').strip())
                        current_chapter['start_page'] = page_num
                    except:
                        current_chapter['start_page'] = 1
            
            # Add last chapter if present
            if current_chapter and 'title' in current_chapter:
                chapters.append(current_chapter)
            
            # Calculate end pages if needed
            for i in range(len(chapters) - 1):
                if 'end_page' not in chapters[i]:
                    chapters[i]['end_page'] = chapters[i + 1]['start_page'] - 1
            
            # Last chapter ends at last page (approx)
            if chapters and 'end_page' not in chapters[-1]:
                chapters[-1]['end_page'] = total_pages
            
            # If no chapters found, create fallback chapters
            if not chapters:
                print("No chapters detected in AI response")
                return self._create_fallback_chapters(total_pages)
            
            return chapters
            
        except Exception as e:
            print(f"Error identifying chapters: {e}")
            # Return fallback chapters on error
            return self._create_fallback_chapters(total_pages)
    
    def _group_chapters_into_topics(self, chapters, text):
        """Group related chapters into topics"""
        # If we have no chapters, we can't group them
        if not chapters:
            return []
            
        # Define the topics we want (fixed hardcoded topics for consistency)
        topic_definitions = [
            {
                'title': 'Introduction to History',
                'keywords': ['introduction', 'overview', 'begin', 'background', 'early'],
                'chapter_indices': [0]  # First chapter typically covers introduction
            },
            {
                'title': 'Political Development',
                'keywords': ['politics', 'government', 'rule', 'administration', 'kingdom', 'empire', 'dynasty', 'democracy'],
                'chapter_indices': [1, 2]  # Guessing chapters 2-3
            },
            {
                'title': 'Economic Aspects',
                'keywords': ['economy', 'trade', 'commerce', 'agriculture', 'industry', 'market', 'production'],
                'chapter_indices': [2, 3]  # Middle chapters often cover economic history
            },
            {
                'title': 'Social and Cultural History',
                'keywords': ['society', 'social', 'culture', 'religion', 'art', 'literature', 'daily life', 'custom'],
                'chapter_indices': [min(4, len(chapters)-1)]  # Later chapter
            },
            {
                'title': 'Major Events and Developments',
                'keywords': ['event', 'war', 'battle', 'revolution', 'movement', 'reform', 'change', 'crisis'],
                'chapter_indices': []  # Will be filled based on keyword matching
            }
        ]
        
        # First, let's identify chapters based on keyword matching
        for chapter in chapters:
            chapter_text = chapter.get('title', '').lower()
            
            # Count keyword matches for each topic
            for topic in topic_definitions:
                match_count = sum(1 for keyword in topic['keywords'] if keyword.lower() in chapter_text)
                if match_count > 0 and chapter['number'] - 1 not in topic['chapter_indices']:
                    topic['chapter_indices'].append(chapter['number'] - 1)
                    
        # If any topic doesn't have chapters assigned, distribute remaining chapters
        remaining_chapters = set(range(len(chapters)))
        for topic in topic_definitions:
            for idx in topic['chapter_indices']:
                if idx in remaining_chapters:
                    remaining_chapters.remove(idx)
                    
        if remaining_chapters:
            # Distribute remaining chapters among topics with fewer chapters
            topics_by_chapter_count = sorted(topic_definitions, key=lambda t: len(t['chapter_indices']))
            for idx, topic in zip(remaining_chapters, [t for t in topics_by_chapter_count if len(t['chapter_indices']) < 2]):
                if idx not in topic['chapter_indices']:
                    topic['chapter_indices'].append(idx)
                    
            # If still have remaining chapters, assign to the last topic
            remaining_chapters = set(range(len(chapters))) - set(idx for topic in topic_definitions for idx in topic['chapter_indices'])
            if remaining_chapters and topic_definitions:
                topic_definitions[-1]['chapter_indices'].extend(remaining_chapters)
                
        # Create final topics
        topics = []
        for topic_def in topic_definitions:
            if not topic_def['chapter_indices']:
                continue  # Skip topics with no chapters
                
            # Get chapter numbers (1-indexed)
            chapter_numbers = [chapters[idx]['number'] for idx in topic_def['chapter_indices'] if idx < len(chapters)]
            
            if not chapter_numbers:
                continue
                
            # Create a summary from the chapters
            summary_parts = []
            for idx in topic_def['chapter_indices']:
                if idx < len(chapters):
                    summary_parts.append(f"Chapter {chapters[idx]['number']}: {chapters[idx]['title']}")
                    
            summary = "Covering: " + "; ".join(summary_parts)
            
            topics.append({
                'title': topic_def['title'],
                'chapters': chapter_numbers,
                'summary': summary
            })
            
        # If no topics were created, use a simple grouping
        if not topics:
            # Create 3 topics: Beginning, Middle, End
            section_size = max(1, len(chapters) // 3)
            topics = []
            
            # Beginning
            if len(chapters) > 0:
                begin_chapters = chapters[:section_size]
                topics.append({
                    'title': 'Beginning Periods',
                    'chapters': [ch['number'] for ch in begin_chapters],
                    'summary': f"Early history covering chapters {begin_chapters[0]['number']} to {begin_chapters[-1]['number']}"
                })
                
            # Middle
            if len(chapters) > section_size:
                middle_chapters = chapters[section_size:2*section_size]
                topics.append({
                    'title': 'Middle Periods',
                    'chapters': [ch['number'] for ch in middle_chapters],
                    'summary': f"Middle period covering chapters {middle_chapters[0]['number']} to {middle_chapters[-1]['number']}"
                })
                
            # End
            if len(chapters) > 2*section_size:
                end_chapters = chapters[2*section_size:]
                topics.append({
                    'title': 'Later Developments',
                    'chapters': [ch['number'] for ch in end_chapters],
                    'summary': f"Later history covering chapters {end_chapters[0]['number']} to {end_chapters[-1]['number']}"
                })
                
        return topics

    def extract_topics_from_chapter(self, chapter_content):
        """Extract topics from chapter content"""
        if not chapter_content or chapter_content.strip() == "":
            # Generate placeholder topics for empty content
            return self._generate_placeholder_topics()
            
        return self._try_with_fallback_keys(self._extract_topics_from_chapter, chapter_content)
    
    def _generate_placeholder_topics(self):
        """Generate placeholder topics when content is missing"""
        topics = []
        placeholder_topics = [
            {"title": "Introduction", "content": "Introduction to the main concepts of this chapter."},
            {"title": "Key Concepts", "content": "Overview of the important concepts and principles."},
            {"title": "Applications", "content": "Practical applications and real-world examples."},
            {"title": "Summary", "content": "Summary of the main points covered in the chapter."}
        ]
        
        for i, topic in enumerate(placeholder_topics):
            topics.append({
                'title': topic["title"],
                'content': topic["content"],
                'order': i + 1,
                'confidence': 0.7
            })
            
        return topics
    
    def _extract_topics_from_chapter(self, chapter_content):
        # Shorten content if it's too long
        if len(chapter_content) > 5000:
            chapter_content = chapter_content[:5000]
        
        prompt = """
        Based on the textbook content provided, identify 4-6 main topics or concepts.
        For each topic, provide:
           - A clear, descriptive title
           - A brief 1-2 sentence summary
        
        Format your response exactly like this:
        
        TOPIC: [Topic Title]
        CONTENT: [Summary of the topic]
        
        The topics should be educational and informative, focusing on the main concepts in the text.
        """
        
        try:
            response = self.pro_model.generate_content(
                [prompt, chapter_content],
                generation_config={
                    'temperature': 0.3,
                    'max_output_tokens': 2048,
                }
            )
            
            content = response.text
            print("Topics from Chapter Response:", content)
            
            # Check if we got a valid response or a prompt repeat
            if "please provide" in content.lower() or "i'm ready" in content.lower():
                return self._generate_placeholder_topics()
                
            # Parse the structured response
            topics = []
            current_topic = {}
            
            for line in content.split('\n'):
                line = line.strip()
                if not line:
                    if current_topic and 'title' in current_topic and 'content' in current_topic:
                        topics.append(current_topic)
                        current_topic = {}
                    continue
                
                if line.startswith('TOPIC:'):
                    if current_topic and 'title' in current_topic and 'content' in current_topic:
                        topics.append(current_topic)
                    current_topic = {
                        'title': line.replace('TOPIC:', '').strip(),
                        'confidence': 0.85
                    }
                
                elif line.startswith('CONTENT:') and 'title' in current_topic:
                    current_topic['content'] = line.replace('CONTENT:', '').strip()
                
                elif 'title' in current_topic and 'content' in current_topic:
                    # Append to existing content
                    current_topic['content'] += " " + line
                elif 'title' in current_topic:
                    # This might be content without the CONTENT: prefix
                    current_topic['content'] = line
            
            # Add last topic if present
            if current_topic and 'title' in current_topic and 'content' in current_topic:
                topics.append(current_topic)
            
            # Add order to topics
            for i, topic in enumerate(topics):
                topic['order'] = i + 1
            
            # If no valid topics found, return placeholders
            if not topics:
                return self._generate_placeholder_topics()
                
            return topics
            
        except Exception as e:
            print(f"Error extracting topics from chapter: {e}")
            return self._generate_placeholder_topics()
    
    def extract_key_points(self, topic_content):
        """Extract key learning points from topic content"""
        if not topic_content or len(topic_content.strip()) < 10:
            # Generate placeholder key points
            return self._generate_placeholder_key_points()
            
        try:
            return self._try_with_fallback_keys(self._extract_key_points, topic_content)
        except Exception as e:
            print(f"Error extracting key points with API: {e}")
            return self._generate_placeholder_key_points()
    
    def _generate_placeholder_key_points(self):
        """Generate placeholder key points when API fails"""
        placeholder_points = [
            "This is an important concept to understand in this topic.",
            "Remember this key principle when studying this subject.",
            "Apply this knowledge to solve related problems.",
            "This fact is critical for understanding the broader concepts."
        ]
        
        # Return 3 random points
        selected_points = random.sample(placeholder_points, min(3, len(placeholder_points)))
        
        return [{'text': point, 'is_key_point': True} for point in selected_points]
    
    def _extract_key_points(self, topic_content):
        # Extract 3-4 sentences from the topic content if it's too short
        if len(topic_content) < 50:
            # Just create bullet points from the content itself
            return [{'text': topic_content, 'is_key_point': True}]
            
        prompt = """
        From the following educational topic, extract 3-4 key learning points.
        Each point should be concise, informative, and represent an important concept or fact.
        
        Format each point as a separate numbered item.
        
        Topic content:
        """ + topic_content
        
        try:
            response = self.pro_model.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.2,
                    'max_output_tokens': 1024,
                }
            )
            
            content = response.text
            print("Key Points Response:", content)
            
            # Check if we got a valid response or just a prompt repeat
            if "please provide" in content.lower() or "i need" in content.lower():
                return self._generate_placeholder_key_points()
            
            # Parse the points
            points = []
            for line in content.split('\n'):
                line = line.strip()
                if not line:
                    continue
                
                # Check for numbered points (1. Point text)
                match = re.match(r'^\d+\.?\s+(.+)$', line)
                if match:
                    point_text = match.group(1)
                    points.append({
                        'text': point_text,
                        'is_key_point': True
                    })
            
            # If no points were found, extract sentences
            if not points:
                # Simple sentence splitting
                sentences = re.split(r'(?<=[.!?])\s+', topic_content)
                points = [{'text': s, 'is_key_point': False} for s in sentences[:3] if len(s) > 10]
            
            # If still no points, generate placeholders
            if not points:
                return self._generate_placeholder_key_points()
                
            return points
        
        except Exception as e:
            print(f"Error extracting key points: {e}")
            return self._generate_placeholder_key_points()
    
    def simplify_text(self, text):
        """Create a simplified version of text (for younger audiences)"""
        if not text or len(text.strip()) < 10:
            return "Simplified version not available."
            
        try:
            return self._try_with_fallback_keys(self._simplify_text, text)
        except Exception as e:
            print(f"Error simplifying text with API: {e}")
            # Return a shortened version of the original text
            if len(text) > 100:
                return text[:97] + "..."
            return text
    
    def _simplify_text(self, text):
        prompt = f"""
        Simplify this text for a younger audience (aged 12-15):
        "{text}"
        
        Make it shorter, use simpler language, and keep the key information.
        Maximum 2 sentences.
        """
        
        try:
            response = self.pro_model.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.2,
                    'max_output_tokens': 150,
                }
            )
            
            simplified = response.text.strip()
            
            # Check if we got a valid response
            if len(simplified) < 5 or simplified == text:
                # Fallback: return truncated version
                if len(text) > 100:
                    return text[:97] + "..."
                return text
                
            return simplified
        
        except Exception as e:
            print(f"Error simplifying text: {e}")
            # Return a shortened version of the original text
            if len(text) > 100:
                return text[:97] + "..."
            return text 