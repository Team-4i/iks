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
        
        if not os.path.exists(page_images_dir):
            print(f"No page images found in {page_images_dir}")
            return None
        
        all_hierarchical_data = []
        
        # Process each image in the page_images directory
        image_files = sorted([f for f in os.listdir(page_images_dir) if f.endswith('.jpg')])
        
        if not image_files:
            print("No image files found in the page_images directory")
            return None
        
        print(f"Processing {len(image_files)} image files for content extraction")
        
        for image_file in image_files:
            image_path = os.path.join(page_images_dir, image_file)
            print(f"Extracting content from {image_path}")
            
            # Extract hierarchical content from this image
            hierarchical_data = self.extract_hierarchical_content(image_path)
            
            if hierarchical_data:
                all_hierarchical_data.extend(hierarchical_data)
        
        # After processing all images, convert the hierarchical data to database format
        if all_hierarchical_data:
            result = self.convert_to_db_format(all_hierarchical_data, pdf_doc)
            
            # After creating topics and chapters, automatically group them
            if result and result.get('topics'):
                # Initialize the topic grouping service
                from .services import TopicGroupingService
                grouping_service = TopicGroupingService()
                
                # Automatically group topics after creation
                created_groups = grouping_service.group_topics(pdf_doc)
                
                return {
                    'topics_count': len(result['topics']),
                    'chapters_count': len(result['chapters']),
                    'groups_count': len(created_groups) if created_groups else 0
                }
            else:
                return {
                    'topics_count': 0,
                    'chapters_count': 0,
                    'groups_count': 0
                }
        else:
            print("No hierarchical data extracted from any images")
            return None
        
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
        from .models import MainTopic, SubTopic
        
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
            "similarity_score": 0.85,  // How closely related these topics are (0.0 to 1.0)
            "sub_topics": [
              {{
                "title": "Sub-topic 1 title",
                "description": "Description of this sub-topic",
                "topic_ids": [list of topic IDs in this sub-topic, must be subset of parent group's topic_ids],
                "relevance_score": 0.9
              }},
              // More sub-topics...
            ]
          }},
          // More groups...
        ]
        ```

        IMPORTANT:
        - Create intuitive, meaningful groups based on subject matter
        - Focus on academic/educational categorization
        - Every topic must be assigned to exactly one group
        - For each group, create 2-3 sub-topics that further categorize the topics
        - Topic IDs in sub-topics must be subsets of the parent group's topic IDs
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
            
            # Delete existing topic groups and sub-topics
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
                
                # Create sub-topics if available in the AI response
                if 'sub_topics' in group_info and group_info['sub_topics']:
                    for sub_idx, sub_topic_info in enumerate(group_info['sub_topics']):
                        # Create the sub-topic
                        sub_topic = SubTopic.objects.create(
                            topic_group=topic_group,
                            title=sub_topic_info['title'],
                            description=sub_topic_info['description'],
                            summary=sub_topic_info.get('description', ''),  # Use description as initial summary
                            relevance_score=float(sub_topic_info.get('relevance_score', 0.8)),
                            order=sub_idx + 1
                        )
                        
                        # Add main topics to the sub-topic
                        sub_topic_ids = sub_topic_info.get('topic_ids', [])
                        main_topics_to_add = topics.filter(id__in=sub_topic_ids)
                        sub_topic.main_topics.add(*main_topics_to_add)
                
                created_groups.append(topic_group)
                
            # After creating main topics and sub-topics, automatically generate relationship data
            self.analyze_topic_relationships(pdf_doc)
                
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