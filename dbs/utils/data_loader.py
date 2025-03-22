import google.generativeai as genai
from django.conf import settings
from django.apps import apps
# from housie_consti.models import Article
import time
import json

class DataLoader:
    _instance = None
    _articles_cache = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            genai.configure(api_key=settings.GOOGLE_API_KEY)
            cls._instance.model = genai.GenerativeModel('gemini-pro')
            cls._instance._refresh_articles_cache()
        return cls._instance

    def _refresh_articles_cache(self):
        """Keep constitutional articles in memory"""
        self._articles_cache = {
            str(article.id): {
                'title': article.title,
                'text': article.content,
                'explanation': article.content
            }
            for article in Article.objects.all()
        }
        print(f"Cached {len(self._articles_cache)} articles")

    def load_data(self, target_model, field_mapping, context, count=5, article_filter=None):
        """
        Load data into any model with specific field mappings
        """
        try:
            # Get relevant articles
            if article_filter:
                relevant_articles = {k:v for k,v in self._articles_cache.items() 
                                   if article_filter(k,v)}
            else:
                relevant_articles = self._articles_cache

            print(f"Using {len(relevant_articles)} relevant articles")

            # Get a default Article instance for foreign key
            from housie_consti.models import Article
            default_article = Article.objects.first()
            if not default_article:
                raise Exception("No Article found in database")

            # Create prompt
            prompt = f"""
            Using these Constitutional Articles as reference:
            {json.dumps(dict(list(relevant_articles.items())[:3]), indent=2)}

            Generate {count} entries for a model with these fields:
            {json.dumps(field_mapping, indent=2)}

            Additional Context:
            {context}

            Return ONLY a valid Python list of dictionaries with these exact field names. Example:
            [
                {{
                    "title": "Example Case vs State (2020)",
                    "description": "Description text here",
                    "year": 2020,
                    "articles_involved": "Article 21"
                }},
                ...
            ]
            
            Important:
            - Use only the exact field names provided
            - No null values, use empty strings or 0 instead
            - Year must be a number between 1950-2024
            - All text fields must be strings
            """

            print("Sending request to Gemini...")
            response = self.model.generate_content(prompt)
            print("Got response from Gemini")

            # Clean and parse the response
            response_text = response.text.strip()
            if response_text.startswith('```') and response_text.endswith('```'):
                response_text = response_text[3:-3]
            if response_text.startswith('python'):
                response_text = response_text[6:]
            
            # Replace null with None
            response_text = response_text.replace('null', 'None')
            
            # Safely evaluate the response
            entries = eval(response_text)
            
            created_objects = []
            for entry in entries:
                # Convert any None values to appropriate defaults
                entry = {k: ('' if v is None and isinstance(field_mapping[k], str) else v) 
                        for k, v in entry.items()}
                
                # Add the Article foreign key
                entry['article'] = default_article
                
                obj = target_model.objects.create(**entry)
                created_objects.append(obj)
                time.sleep(0.5)

            return {
                'success': True,
                'message': f'Created {len(created_objects)} {target_model._meta.verbose_name} entries',
                'objects': created_objects
            }

        except Exception as e:
            print(f"Error in load_data: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def direct_article_load(self, target_model, field_mapping, article_numbers=None):
        """
        Load data directly from constitutional articles
        
        Example field_mapping:
        {
            'title': 'article_title',
            'content': 'original_text',
            'summary': 'simplified_explanation',
            'number': 'article_number'
        }
        """
        try:
            articles = self._articles_cache
            if article_numbers:
                articles = {k:v for k,v in articles.items() if k in article_numbers}

            created_objects = []
            for article_id, data in articles.items():
                entry = {}
                for field, source in field_mapping.items():
                    if source in data:
                        entry[field] = data[source]
                    elif source == 'article_id':
                        entry[field] = article_id

                obj = target_model.objects.create(**entry)
                created_objects.append(obj)

            return {
                'success': True,
                'message': f'Loaded {len(created_objects)} entries directly from articles',
                'objects': created_objects
            }

        except Exception as e:
            print(f"Error in direct_article_load: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            } 

# Initialize the loader
# data_loader = DataLoader()

# Map the field types to your actual Case model fields
case_mapping = {
    'title': 'article_based_title',  # This will generate a title
    'description': 'detailed_explanation',  # This will generate description
    'year': 'year_between_1950_2024',  # This will generate year
    'articles_involved': 'direct_article_number',  # This will use article numbers
    'article_id': 'article_reference'  # This will link to Article model
}

context = """
Create legal cases that:
- Focus on fundamental rights violations
- Include real-world scenarios
- Reference Supreme Court judgments
- Include year between 1950-2024
- Format title as 'Case Name vs State/Party (Year)'
"""

# Let's see your Case model fields first
# from housie_consti.models import Case
# print("Available Case model fields:")
# for field in Case._meta.fields:
#     print(f"- {field.name} ({field.get_internal_type()})")

# Now try loading data with correct field names
# print("\nStarting data load...")
# result = data_loader.load_data(
#     target_model=Case,
#     field_mapping={
#         'title': 'title',  # Using exact field names from your model
#         'description': 'description',
#         'year': 'year',
#         'articles_involved': 'articles_involved',
#         'article_id': '1'  # Default article ID
#     },
#     context=context,
#     count=2
# )

# print(result['message'] if result['success'] else f"Error: {result['error']}")