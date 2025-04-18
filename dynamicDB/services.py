import google.generativeai as genai
from PIL import Image
import os
import random
from collections import defaultdict
import re
import json

class TextbookAnalyzer:
    def __init__(self):
        # Configure Gemini AI with direct API key
        genai.configure(api_key="AIzaSyA3CUAY0wSBFA_hOztQh19-QUy2QpA6VDQ")
        # Use gemini-2.0-flash model
        self.model = genai.GenerativeModel('gemini-2.0-flash')

    def extract_hierarchical_content(self, image_path):
        """Extract topics and their chapters hierarchically from a document image"""
        try:
            # Load and prepare the image
            img = Image.open(image_path)
            
            # Lecture-oriented extraction prompt
            prompt = """
            You are given a PDF containing a lecture or textbook content.

            Your task:
            1. Identify broad topics or themes that appear as slide titles or section headers (e.g., "Ṛgveda", "Upaniṣads", "Vedāṅgas", etc.). Treat each of these as a Topic.
            2. Under each Topic, list the specific concepts, bullet points, or definitions shown in the slides that fall under that theme. Treat each of these as Chapters.

            Output format:
            Topic: [Main Theme Title]
            - Chapter: [Sub-concept 1]
            - Chapter: [Sub-concept 2]

            (Leave a blank line between topics)

            IMPORTANT:
            🧠 Do not include summaries or extra information.
            ✅ Only extract titles and structured headers as they appear.
            ✅ Avoid confidence scores or interpretations.
            ✅ If there's no clear sub-concept list, treat the topic itself as a single chapter.
            """

            # Generate response from Gemini
            response = self.model.generate_content(
                [prompt, img],
                generation_config={
                    'temperature': 0.1,  # Lower temperature for more structured results
                    'candidate_count': 1,
                    'max_output_tokens': 2048,
                }
            )
            
            content = response.text
            print("Gemini Response for Hierarchical Content:", content)  # Debug print
            
            # Process the hierarchical response
            topics = []
            current_topic = None
            current_chapters = []
            
            # Parse the response
            lines = content.split('\n')
            for line in lines:
                line = line.strip()
                if not line:
                    # Save current topic if it exists and start a new one
                    if current_topic:
                        topics.append({
                            'title': current_topic,
                            'chapters': current_chapters.copy(),
                            'order': len(topics) + 1
                        })
                        current_topic = None
                        current_chapters = []
                    continue
                
                # Check if this is a topic line
                if line.startswith('Topic:'):
                    # Save previous topic if it exists
                    if current_topic:
                        topics.append({
                            'title': current_topic,
                            'chapters': current_chapters.copy(),
                            'order': len(topics) + 1
                        })
                        current_chapters = []
                    
                    # Extract new topic
                    current_topic = line.replace('Topic:', '').strip()
                
                # Check if this is a chapter line (updated format)
                elif line.startswith('- Chapter:') or line.startswith('-Chapter:'):
                    # Extract chapter information
                    chapter_title = line.replace('- Chapter:', '').replace('-Chapter:', '').strip()
                    
                    # Add chapter to current list with sequential number as a string
                    chapter_number = str(len(current_chapters) + 1)
                    current_chapters.append({
                        'number': chapter_number,
                        'title': chapter_title,
                        'order': len(current_chapters) + 1
                    })
            
            # Add the last topic if there is one
            if current_topic:
                topics.append({
                    'title': current_topic,
                    'chapters': current_chapters,
                    'order': len(topics) + 1
                })
            
            # Handle edge case: if no structured content was found
            if not topics and content.strip():
                # Try to find any headings in the unstructured text
                potential_headings = re.findall(r'(?:\d+\.)*\s*[\w\s:]+', content)
                if potential_headings:
                    topics.append({
                        'title': potential_headings[0].strip(),
                        'chapters': [{'number': '1', 'title': h.strip(), 'order': i+1} 
                                   for i, h in enumerate(potential_headings[1:])],
                        'order': 1
                    })
                else:
                    # Last resort: just use the whole content as a single topic
                    topics.append({
                    'title': 'Main Content',
                        'chapters': [{'number': '1', 'title': 'Content', 'order': 1}],
                        'order': 1
                })
            
            return topics
                
        except Exception as e:
            print(f"Hierarchical Extraction Error: {str(e)}")
            return [{
                'title': 'Processing Notice',
                'chapters': [{
                    'number': '0',
                    'title': f'Error: {str(e)}',
                    'order': 1
                }],
                'order': 1
            }]
    
    def convert_to_db_format(self, hierarchical_data, pdf_document):
        """
        Convert hierarchical topics and chapters to database format.
        This creates Topic and Chapter objects from the hierarchical data.
        """
        from .models import Topic, Chapter
        
        created_topics = []
        created_chapters = []
        
        # Delete existing data for this document
        Topic.objects.filter(pdf_document=pdf_document).delete()
        Chapter.objects.filter(pdf_document=pdf_document).delete()
        
        # Process each topic and its chapters
        for topic_data in hierarchical_data:
            # Create the main topic
            main_topic = Topic.objects.create(
                pdf_document=pdf_document,
                title=topic_data['title'],
                summary=f"Main topic containing {len(topic_data['chapters'])} chapters",
                order=topic_data['order']
            )
            created_topics.append(main_topic)
            
            # Create chapters for this topic
            for chapter_data in topic_data['chapters']:
                chapter = Chapter.objects.create(
                    pdf_document=pdf_document,
                    title=f"{chapter_data['number']} {chapter_data['title']}".strip(),
                    content=f"Subheading of {topic_data['title']}",
                    start_page=1,  # Default value
                    end_page=1,    # Default value
                    confidence_score=0.9,
                    order=chapter_data['order']
                )
                created_chapters.append(chapter)
                
                # Associate chapter with topic
                main_topic.chapters.add(chapter)
        
        return {
            'topics': created_topics,
            'chapters': created_chapters
        }
    
    def process_document(self, pdf_doc):
        """Process a PDF document by extracting hierarchical content and saving to database."""
        # Import models
        from .models import Topic, Chapter
        from django.conf import settings
        import os
        
        # Check if there are page_images in the temp directory
        temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp', f'pdf_{pdf_doc.id}')
        page_images_dir = os.path.join(temp_dir, 'page_images')
        
        all_hierarchical_data = []
        
        if os.path.exists(page_images_dir):
            print(f"Found page images directory: {page_images_dir}")
            # Get all image files
            image_files = sorted([f for f in os.listdir(page_images_dir) if f.endswith('.jpg')])
            
            if image_files:
                print(f"Found {len(image_files)} image files for analysis")
                
                # Process each image group and combine results
                for i, img_file in enumerate(image_files):
                    img_path = os.path.join(page_images_dir, img_file)
                    print(f"Analyzing image {i+1}/{len(image_files)}: {img_path}")
                    
                    # Extract topics from this image
                    try:
                        topics = self.extract_hierarchical_content(img_path)
                        if topics:
                            for topic in topics:
                                # Check if this topic already exists in our results (by title similarity)
                                topic_exists = False
                                for existing_topic in all_hierarchical_data:
                                    # Simple string similarity check (can be improved)
                                    if existing_topic['title'].lower() == topic['title'].lower():
                                        # Merge chapters instead of duplicating the topic
                                        existing_topic['chapters'].extend(topic['chapters'])
                                        topic_exists = True
                                        break
                                
                                if not topic_exists:
                                    all_hierarchical_data.append(topic)
                    except Exception as e:
                        print(f"Error analyzing image {img_file}: {str(e)}")
                
                # Now adjust order numbers to be sequential
                for i, topic in enumerate(all_hierarchical_data):
                    topic['order'] = i + 1
                    
                    # Adjust chapter order to be sequential within each topic
                    for j, chapter in enumerate(topic['chapters']):
                        chapter['order'] = j + 1
            else:
                # Fallback to the preview image
                print(f"No image files found, using converted image: {pdf_doc.converted_image.path}")
                all_hierarchical_data = self.extract_hierarchical_content(pdf_doc.converted_image.path)
        else:
            # Fallback to the preview image
            print(f"No page_images directory found, using converted image: {pdf_doc.converted_image.path}")
            all_hierarchical_data = self.extract_hierarchical_content(pdf_doc.converted_image.path)
        
        # Debug print the extracted hierarchical data
        print(f"Extracted {len(all_hierarchical_data)} topics:")
        for i, topic in enumerate(all_hierarchical_data):
            print(f"  Topic {i+1}: {topic['title']}")
            print(f"    Chapters: {len(topic['chapters'])}")
            for j, chapter in enumerate(topic['chapters']):
                print(f"      Chapter {j+1}: {chapter.get('number', 'N/A')} - {chapter['title']}")
        
        # Delete existing chapters and topics for this document
        print(f"Deleting existing topics and chapters for document {pdf_doc.id}")
        pdf_doc.chapters.all().delete()
        pdf_doc.main_topics.all().delete()
        
        # Track counts for return
        topics_count = 0
        chapters_count = 0
        
        # Save topics and chapters to database
        print("Creating new topics and chapters...")
        for topic_data in all_hierarchical_data:
            # Create Topic
            main_topic = Topic.objects.create(
                pdf_document=pdf_doc,
                title=topic_data['title'],
                summary=topic_data.get('summary', f"Main topic containing {len(topic_data['chapters'])} chapters"),
                order=topic_data['order']
            )
            topics_count += 1
            print(f"Created topic: {main_topic.title} (ID: {main_topic.id})")
            
            # Create chapters for this topic
            for chapter_idx, chapter_data in enumerate(topic_data['chapters']):
                # For lecture-oriented content, we just use the title directly
                chapter = Chapter.objects.create(
                    pdf_document=pdf_doc,
                    title=chapter_data['title'],
                    content=chapter_data.get('content', f"Subheading of {topic_data['title']}"),
                    start_page=chapter_data.get('start_page', 1),
                    end_page=chapter_data.get('end_page', 1),
                    confidence_score=chapter_data.get('confidence', 0.8),
                    order=chapter_idx + 1
                )
                chapters_count += 1
                print(f"  Created chapter: {chapter.title} (ID: {chapter.id})")
                
                # Add chapter to topic
                main_topic.chapters.add(chapter)
                print(f"  Associated chapter with topic")
        
        print(f"Created {topics_count} topics and {chapters_count} chapters")
        
        return {
            'topics_count': topics_count,
            'chapters_count': chapters_count
        }
        
    # Legacy methods kept for backward compatibility
    
    def extract_chapters(self, image_path):
        """Legacy method for extracting chapters"""
        topics = self.extract_hierarchical_content(image_path)
        
        # Flatten chapters from all topics
        chapters = []
        for topic_idx, topic in enumerate(topics):
            for chapter_idx, chapter in enumerate(topic['chapters']):
                chapters.append({
                    'order': len(chapters) + 1,
                    'title': f"{chapter['number']} {chapter['title']}".strip(),
                    'content': f"From topic: {topic['title']}",
                    'confidence': 0.9
                })
        
        # If no chapters were found, create a default one
        if not chapters:
            chapters.append({
                'order': 1,
                'title': 'Main Content',
                'content': 'No chapters were detected in the document.',
                'confidence': 0.5
            })
        
        return chapters
    
    def group_chapters_into_topics(self, chapters, desired_topic_count=3):
        """Legacy method for backward compatibility"""
        # Use the hierarchical extraction instead, but format to match the expected output
        if not chapters:
            return []
            
        # For the new approach, we don't need this method as topics are already extracted
        # But for backward compatibility, we'll create "artificial" topic groupings
        
        # Group chapters evenly
        chapters_per_topic = max(1, len(chapters) // desired_topic_count)
        
        topics = []
        for i in range(desired_topic_count):
            start_idx = i * chapters_per_topic
            end_idx = start_idx + chapters_per_topic if i < desired_topic_count - 1 else len(chapters)
            
            if start_idx >= len(chapters):
                break
                
            chapters_for_topic = chapters[start_idx:end_idx]
            
            # Generate a title based on the chapters
            if len(chapters_for_topic) == 1:
                topic_title = chapters_for_topic[0]['title']
            else:
                first_title = chapters_for_topic[0]['title']
                last_title = chapters_for_topic[-1]['title']
                topic_title = f"{first_title} to {last_title}"
            
            # Create a summary
            chapter_titles = [ch['title'] for ch in chapters_for_topic]
            summary = f"Group containing: {', '.join(chapter_titles)}"
            
            topics.append({
                'order': i + 1,
                'title': topic_title[:50],  # Limit to 50 chars
                'summary': summary,
                'chapters': chapters_for_topic,
                'chapter_ids': [ch['order'] for ch in chapters_for_topic]
            })
        
        return topics
    
    def analyze_document(self, image_path):
        """Legacy method for backward compatibility"""
        return self.extract_chapters(image_path)
        
    # Helper methods
    
    def _find_common_theme(self, chapters):
        """Legacy helper method kept for backward compatibility"""
        return "Common Theme"
    
    def _generate_fallback_summary(self, chapters):
        """Legacy helper method kept for backward compatibility"""
        return "Group of related chapters"
    
    def _fallback_topic_grouping(self, chapters, desired_topic_count):
        """Legacy helper method kept for backward compatibility"""
        return self.group_chapters_into_topics(chapters, desired_topic_count)

class TopicGroupingService:
    """Service to analyze and group related topics using AI"""
    
    def __init__(self):
        # Configure Gemini AI with direct API key
        genai.configure(api_key="AIzaSyA3CUAY0wSBFA_hOztQh19-QUy2QpA6VDQ")
        # Use gemini-2.0-flash model
        self.model = genai.GenerativeModel('gemini-2.0-flash')
    
    def group_topics(self, pdf_doc):
        """
        Analyze topics in the PDF document and group them hierarchically
        
        Args:
            pdf_doc: PDFDocument instance with extracted topics
            
        Returns:
            List of MainTopic objects
        """
        from .models import MainTopic
        
        # Get all topics for this document
        topics = pdf_doc.main_topics.all().prefetch_related('chapters')
        
        if not topics:
            print("No topics found to group")
            return []
            
        # Format topics and their chapters for the AI model
        topics_data = []
        for topic in topics:
            chapters_list = [ch.title for ch in topic.chapters.all()]
            topics_data.append({
                'id': topic.id,
                'title': topic.title,
                'chapters': chapters_list
            })
            
        print(f"Analyzing {len(topics_data)} topics for grouping")
        
        # Create the prompt for Gemini
        topics_json = json.dumps(topics_data, indent=2)
        prompt = f"""
        You are given a list of educational topics extracted from a textbook or lecture.
        Your task is to analyze these topics and group them into broader categories or themes.

        The topics data is provided in JSON format:
        {topics_json}

        Each topic has:
        - id: A unique identifier
        - title: The topic title
        - chapters: A list of chapter titles under this topic

        Based on semantic similarity and thematic relationships, group these topics into 3-5 meaningful categories.

        Return your response in the following JSON format:
        ```
        [
          {{
            "group_title": "Name of Group 1",
            "description": "Brief description of what unifies these topics",
            "keywords": "comma,separated,keywords",
            "topic_ids": [list of topic IDs in this group],
            "similarity_score": 0.85  // How closely related these topics are (0.0 to 1.0)
          }},
          // More groups...
        ]
        ```

        IMPORTANT:
        - Create intuitive, meaningful groups based on subject matter
        - Focus on academic/educational categorization
        - Every topic must be assigned to exactly one group
        - Return valid JSON format only
        """
        
        try:
            # Generate response from Gemini
            response = self.model.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.2,
                    'candidate_count': 1,
                    'max_output_tokens': 4096,
                }
            )
            
            content = response.text
            print("Gemini Response for Topic Grouping:", content)
            
            # Extract JSON from response
            if '```' in content:
                json_content = content.split('```')[1]
                if json_content.startswith('json'):
                    json_content = json_content[4:].strip()
            else:
                json_content = content.strip()
                
            # Parse the JSON
            group_data = json.loads(json_content)
            
            # Delete existing topic groups
            pdf_doc.topic_groups.all().delete()
            
            # Create topic groups based on AI response
            created_groups = []
            for idx, group_info in enumerate(group_data):
                # Create the topic group
                topic_group = MainTopic.objects.create(
                    pdf_document=pdf_doc,
                    title=group_info['group_title'],
                    description=group_info['description'],
                    keywords=group_info.get('keywords', ''),
                    similarity_score=float(group_info.get('similarity_score', 0.7)),
                    order=idx + 1
                )
                
                # Add topics to the group
                topic_ids = group_info['topic_ids']
                topics_to_add = topics.filter(id__in=topic_ids)
                topic_group.topics.add(*topics_to_add)
                
                created_groups.append(topic_group)
                
            return created_groups
                
        except Exception as e:
            print(f"Error in topic grouping: {str(e)}")
            import traceback
            traceback.print_exc()
            return []
            
    def analyze_topic_relationships(self, pdf_doc):
        """
        Analyze relationships between topics and create a hierarchical structure
        
        Args:
            pdf_doc: PDFDocument instance with extracted topics
            
        Returns:
            Dictionary with relationship data
        """
        topic_groups = pdf_doc.topic_groups.all().prefetch_related('topics')
        
        if not topic_groups:
            print("No topic groups found for relationship analysis")
            return {}
            
        # Format topic groups for the AI model
        groups_data = []
        for group in topic_groups:
            topics_list = [{"id": t.id, "title": t.title} for t in group.topics.all()]
            groups_data.append({
                'id': group.id,
                'title': group.title,
                'description': group.description,
                'topics': topics_list
            })
            
        # Create the prompt for relationship analysis
        groups_json = json.dumps(groups_data, indent=2)
        prompt = f"""
        You are analyzing educational content that has been organized into topic groups.
        Your task is to identify the relationships and hierarchical structure between these groups.

        The topic groups data is provided in JSON format:
        {groups_json}

        Based on the content and relationships, please:
        1. Identify any hierarchical relationships (parent-child) between the groups
        2. Identify any prerequisites or sequential learning order
        3. Create a knowledge graph showing how these topics interconnect

        Return your analysis in the following JSON format:
        ```json
        {{
          "hierarchy": [
            {{
              "parent_id": null,  // null means top-level group
              "group_id": 1,
              "children": [2, 3]  // IDs of child groups, if any
            }},
            // More groups...
          ],
          "learning_sequence": [1, 2, 3],  // Suggested learning order by group ID
          "relationships": [
            {{
              "from_id": 1,
              "to_id": 2,
              "relationship_type": "prerequisite", // or "related", "builds_upon", etc.
              "strength": 0.8  // How strong the relationship is (0.0 to 1.0)
            }},
            // More relationships...
          ]
        }}
        ```

        IMPORTANT:
        - Focus on creating a meaningful structure for learning
        - Return valid JSON format only
        """
        
        try:
            # Generate response from Gemini
            response = self.model.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.2,
                    'candidate_count': 1,
                    'max_output_tokens': 4096,
                }
            )
            
            content = response.text
            print("Gemini Response for Relationship Analysis:", content)
            
            # Extract JSON from response
            if '```' in content:
                json_content = content.split('```')[1]
                if json_content.startswith('json'):
                    json_content = json_content[4:].strip()
            else:
                json_content = content.strip()
                
            # Parse the JSON
            relationship_data = json.loads(json_content)
            
            # Update parent-child relationships
            hierarchy = relationship_data.get('hierarchy', [])
            for item in hierarchy:
                if item['parent_id'] is None:
                    continue  # Skip top-level groups
                    
                try:
                    # Set parent relationship
                    child_group = MainTopic.objects.get(id=item['group_id'], pdf_document=pdf_doc)
                    parent_group = MainTopic.objects.get(id=item['parent_id'], pdf_document=pdf_doc)
                    child_group.parent = parent_group
                    child_group.save()
                except Exception as e:
                    print(f"Error setting parent-child relationship: {str(e)}")
            
            return relationship_data
                
        except Exception as e:
            print(f"Error in relationship analysis: {str(e)}")
            import traceback
            traceback.print_exc()
            return {}