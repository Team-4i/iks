import os
from groq import Groq
from dotenv import load_dotenv
from django.conf import settings

load_dotenv()  # Load environment variables from .env file

# Generation settings for Gemini
generation_config = {
    "temperature": 0.9,
    "top_p": 1,
    "top_k": 1,
    "max_output_tokens": 2048,
}

class TextGenerationService:
    def __init__(self):
        api_key = settings.GROQ_API_KEY
        if not api_key:
            raise ValueError("GROQ_API_KEY not found in settings")
        self.client = Groq(api_key=api_key)

    def generate_response(self, user_input: str) -> str:
        try:
            if not user_input:
                return "Please provide some input."
            
            context = f"User:{user_input}\nAssistant:"
            
            chat_completion = self.client.chat.completions.create(
                messages=[{
                    "role": "user",
                    "content": context
                }],
                model="mixtral-8x7b-32768",
                temperature=0.9,
                max_tokens=2048,
            )
            
            if not chat_completion or not chat_completion.choices:
                return "I apologize, but I was unable to generate a response."
            
            return chat_completion.choices[0].message.content
        except Exception as e:
            print(f"Error in generate_response: {str(e)}")
            return "I encountered an error while processing your request. Please try again." 