import os
from django.conf import settings
import google.generativeai as genai

# Generation settings for Gemini
generation_config = {
    "temperature": 0.9,
    "top_p": 1,
    "top_k": 1,
    "max_output_tokens": 2048,
}

class TextGenerationService:
    def __init__(self):
        api_key = settings.GOOGLE_API_KEY
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in settings")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash')

    def generate_response(self, user_input: str) -> str:
        try:
            if not user_input:
                return "Please provide some input."
            
            context = f"User:{user_input}\nAssistant:"
            
            response = self.model.generate_content(
                context,
                generation_config=generation_config
            )
            
            if not response:
                return "I apologize, but I was unable to generate a response."
            
            return response.text
        except Exception as e:
            print(f"Error in generate_response: {str(e)}")
            return "I encountered an error while processing your request. Please try again." 