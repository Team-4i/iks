import google.generativeai as genai
from django.conf import settings
import random
import json
from django.db import transaction
import traceback
from dbs.models import ConstitutionalArticle

class GeminiHelper:
    _instance = None
    _constitutional_articles_cache = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # Configure Gemini API once
            genai.configure(api_key=settings.GOOGLE_API_KEY)
            cls._instance.model = genai.GenerativeModel('gemini-pro')
            # Initialize the constitutional articles cache
            cls._instance._refresh_articles_cache()
        return cls._instance

    def _refresh_articles_cache(self):
        """Refresh the cache of constitutional articles"""
        self._constitutional_articles_cache = {
            article.article_number: {
                'title': article.article_title,
                'text': article.original_text,
                'explanation': article.simplified_explanation
            }
            for article in ConstitutionalArticle.objects.all()
        }

    def get_article_context(self, article_numbers=None):
        """Get context from specific articles or all articles"""
        if not self._constitutional_articles_cache:
            self._refresh_articles_cache()
            
        if article_numbers:
            return {num: self._constitutional_articles_cache[num] 
                   for num in article_numbers 
                   if num in self._constitutional_articles_cache}
        return self._constitutional_articles_cache

    def generate_data(self, prompt, **kwargs):
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Error generating content: {str(e)}"

    def generate_python_code(self, prompt, context=None):
        try:
            full_prompt = f"""
            You are a Django developer. Write Python code for the following task:
            
            Context:
            {context if context else 'No specific context provided'}
            
            Task:
            {prompt}
            
            Provide only the executable Python code without any explanations.
            """
            response = self.model.generate_content(full_prompt)
            return response.text
        except Exception as e:
            return f"# Error generating code: {str(e)}"

    def generate_test_data(self, model_info, count=10):
        try:
            prompt = f"""
            Generate {count} test data entries for a Django model with these fields:
            {json.dumps(model_info, indent=2)}
            
            Return only the Python code that creates these entries using Django ORM.
            """
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"# Error generating test data: {str(e)}"

    def analyze_error(self, code, error_message, traceback):
        try:
            prompt = f"""
            As a Django developer, analyze this error and suggest a fix:

            Code:
            {code}

            Error:
            {error_message}

            Traceback:
            {traceback}

            Provide:
            1. The corrected code only
            2. Keep all imports and working parts
            3. Fix only the problematic parts
            """
            
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"# Error analyzing code: {str(e)}"

    def improve_code(self, code, context=None):
        try:
            prompt = f"""
            Improve this Django code by:
            1. Adding error handling
            2. Optimizing database queries
            3. Following Django best practices

            Code:
            {code}

            Context:
            {context if context else 'No specific context provided'}

            Return only the improved code without explanations.
            """
            
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"# Error improving code: {str(e)}"

    def generate_model_data(self, target_model, context, article_numbers=None, count=1):
        """
        Dynamically generate data for any model using Constitutional Articles as context
        
        Args:
            target_model: The Django model to generate data for
            context: User's specific requirements for data generation
            article_numbers: List of specific article numbers to use as context
            count: Number of entries to generate
        """
        try:
            # Get model fields info excluding auto fields
            fields_info = []
            for field in target_model._meta.fields:
                if not field.auto_created:
                    field_type = field.get_internal_type()
                    constraints = []
                    if hasattr(field, 'max_length'):
                        constraints.append(f"max_length={field.max_length}")
                    if field.choices:
                        constraints.append(f"choices={[choice[0] for choice in field.choices]}")
                    if field.related_model:
                        constraints.append(f"related_to={field.related_model._meta.model_name}")
                    
                    field_info = f"{field.name} ({field_type}"
                    if constraints:
                        field_info += f", {', '.join(constraints)}"
                    field_info += ")"
                    fields_info.append(field_info)

            # Get relevant constitutional articles
            articles_context = self.get_article_context(article_numbers)
            
            # Create detailed prompt for Gemini
            prompt = f"""
            Task: Generate data for a Django model using Constitutional Articles as reference.

            Available Constitutional Articles Context:
            {json.dumps(articles_context, indent=2)}

            Target Model Fields:
            {json.dumps(fields_info, indent=2)}

            User Requirements:
            {context}

            Generate {count} entries that:
            1. Match the field types exactly
            2. Respect all field constraints
            3. Use relevant constitutional articles as context
            4. Follow the user requirements
            5. Create meaningful relationships if foreign keys exist

            Return the data in this exact Python dictionary format:
            [
                {{
                    'field_name': 'value',  // Match field type exactly
                    ...
                }},
                ...
            ]
            """

            response = self.model.generate_content(prompt)
            data = eval(response.text)  # Convert string response to Python object
            
            # Create model instances with transaction safety
            created_objects = []
            with transaction.atomic():
                for entry in data:
                    obj = target_model(**entry)
                    obj.full_clean()  # Validate all fields
                    obj.save()
                    created_objects.append(obj)
            
            return {
                'success': True,
                'message': f'Created {len(created_objects)} {target_model._meta.verbose_name} entries',
                'objects': created_objects,
                'articles_used': list(articles_context.keys())
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'traceback': traceback.format_exc()
            }

    def refresh_knowledge(self):
        """Manually refresh the constitutional articles cache"""
        self._refresh_articles_cache()
        return {
            'success': True,
            'message': f'Refreshed knowledge base with {len(self._constitutional_articles_cache)} articles'
        }