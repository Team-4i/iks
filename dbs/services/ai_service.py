import google.generativeai as genai
from django.conf import settings

class GeminiService:
    def __init__(self):
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        self.model = genai.GenerativeModel('gemini-pro')

    def get_code_suggestion(self, prompt, model_info):
        try:
            context = f"""
            Available Models and their fields:
            {model_info}
            
            Task: {prompt}
            
            Please provide Python code that accomplishes this task using Django ORM.
            """
            
            response = self.model.generate_content(context)
            return {
                'success': True,
                'code': response.text,
                'error': None
            }
        except Exception as e:
            return {
                'success': False,
                'code': None,
                'error': str(e)
            } 