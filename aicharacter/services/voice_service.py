import os
from dotenv import load_dotenv
from elevenlabs import ElevenLabs
import base64
from django.conf import settings

load_dotenv()  # Load environment variables from .env file

class VoiceService:
    def __init__(self):
        # Direct API key usage (for testing only)
        self.api_key = "sk_f1980516dc9b2495fd7f10e30761624dfaab6bbdd3126141"
        self.eleven = ElevenLabs(api_key=self.api_key)

    def text_to_speech(self, text: str) -> tuple:
        try:
            if not text:
                return None, "No text provided"
            
            # Generate audio using the client
            voice = self.eleven.voices.get("21m00Tcm4TlvDq8ikWAM")  # Rachel voice ID
            audio = self.eleven.generate(
                text=text,
                voice=voice,
                model="eleven_multilingual_v2",
                stability=0.5,
                similarity_boost=0.75
            )
            
            # Convert audio bytes to base64 string
            audio_base64 = base64.b64encode(audio).decode('utf-8')
            return audio_base64, None
            
        except Exception as e:
            print(f"Error in text_to_speech: {str(e)}")
            return None, str(e) 