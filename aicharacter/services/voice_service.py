import os
from dotenv import load_dotenv
from elevenlabs import ElevenLabs, VoiceSettings
from django.conf import settings
import base64

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
            
            # Use Adam voice (male voice) instead of Rachel
            voice = self.eleven.voices.get("pNInz6obpgDQGcFmaJgB")  # Adam voice ID
            
            # Create voice settings
            voice_settings = VoiceSettings(
                stability=0.5,
                similarity_boost=0.75
            )
            
            # Generate audio with voice settings
            audio_generator = self.eleven.generate(
                text=text,
                voice=voice,
                model="eleven_multilingual_v2",
                voice_settings=voice_settings
            )
            
            # Convert generator to bytes
            audio_bytes = b''.join(audio_generator)
            
            # Convert audio bytes to base64 string
            audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
            return audio_base64, None
            
        except Exception as e:
            print(f"Error in text_to_speech: {str(e)}")
            return None, str(e) 