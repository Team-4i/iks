import google.generativeai as genai
from PIL import Image
import os

class TextbookAnalyzer:
    def __init__(self):
        # Configure Gemini AI with direct API key
        genai.configure(api_key="AIzaSyA3CUAY0wSBFA_hOztQh19-QUy2QpA6VDQ")
        # Use gemini-1.5-flash model
        self.model = genai.GenerativeModel('gemini-1.5-flash')

    def analyze_document(self, image_path):
        """Analyze document using Gemini AI"""
        try:
            # Load and prepare the image
            img = Image.open(image_path)
            
            # Updated prompt to request shorter summaries
            prompt = """
            You are a textbook analyzer. Please analyze this textbook image and identify the main topics or sections in order of appearance.
            For each distinct topic or section you find, provide:
            1. A clear, concise title (max 50 characters)
            2. A brief, single-sentence summary of the content (max 100 characters)
            3. The order number (starting from 1)

            Format each topic exactly like this:
            Order: [Number]
            Topic: [Title]
            Content: [Summary]

            Guidelines:
            - List topics in the exact order they appear in the text
            - Focus on the most essential point only
            - Keep titles very short but descriptive
            - Ensure summaries are concise and fit on a single card
            - Separate different topics with a blank line
            - Always include the Order number
            - Limit content to one clear, focused sentence
            """

            # Generate response from Gemini with optimized settings for flash model
            response = self.model.generate_content(
                [prompt, img],
                generation_config={
                    'temperature': 0.1,  # Lower temperature for more focused results
                    'candidate_count': 1,
                    'max_output_tokens': 1024,
                }
            )
            
            content = response.text
            print("Gemini Response:", content)  # Debug print
            
            # Process the response into topics
            topics = []
            current_topic = None
            current_content = []
            current_order = None
            
            for line in content.split('\n'):
                line = line.strip()
                if not line:  # Skip empty lines
                    continue
                
                if line.startswith('Order:'):
                    # Save previous topic if exists
                    if current_topic and current_content:
                        # Truncate content if too long
                        combined_content = ' '.join(current_content)
                        if len(combined_content) > 100:
                            combined_content = combined_content[:97] + '...'
                        
                        topics.append({
                            'order': current_order or len(topics) + 1,
                            'title': (current_topic[:47] + '...') if len(current_topic) > 50 else current_topic,
                            'content': combined_content,
                            'confidence': 0.9
                        })
                    # Start new topic
                    try:
                        current_order = int(line.replace('Order:', '').strip())
                    except ValueError:
                        current_order = len(topics) + 1
                    current_topic = None
                    current_content = []
                elif line.startswith('Topic:'):
                    current_topic = line.replace('Topic:', '').strip()
                elif line.startswith('Content:'):
                    current_content = [line.replace('Content:', '').strip()]
                elif current_topic:  # Add to current content if we have a topic
                    current_content.append(line)
            
            # Add the last topic
            if current_topic and current_content:
                topics.append({
                    'order': current_order or len(topics) + 1,
                    'title': current_topic,
                    'content': ' '.join(current_content),
                    'confidence': 0.9
                })
            
            # Sort topics by order
            topics.sort(key=lambda x: x['order'])
            
            # Fallback if no topics were found
            if not topics and content:
                topics.append({
                    'order': 1,
                    'title': 'Main Content',
                    'content': content,
                    'confidence': 0.8
                })
            
            return topics
                
        except Exception as e:
            print(f"Analysis Error: {str(e)}")
            return [{
                'order': 1,
                'title': 'Processing Notice',
                'content': f'The system encountered an issue while analyzing the content: {str(e)}. Please ensure the image is clear and try again.',
                'confidence': 0.5
            }] 