from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from .services.text_generation import TextGenerationService
from .services.voice_service import VoiceService
from django.conf import settings
import logging

text_generation_service = TextGenerationService()
voice_service = VoiceService()

logger = logging.getLogger(__name__)

def index(request):
    return render(request, 'aicharacter/index.html')

@csrf_exempt
def get_response(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_input = data.get('user_input', '').strip()
            if user_input:
                response_text = text_generation_service.generate_response(user_input)
                return JsonResponse({"response": response_text})
            return JsonResponse({"error": "No input provided"}, status=400)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
    return JsonResponse({"error": "Method not allowed"}, status=405)

@csrf_exempt
def text_to_speech(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            text = data.get('text', '').strip()
            if text:
                audio, error = voice_service.text_to_speech(text)
                if error:
                    return JsonResponse({"error": error}, status=500)
                return JsonResponse({"audio": audio})
            return JsonResponse({"error": "No text provided"}, status=400)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
    return JsonResponse({"error": "Method not allowed"}, status=405)

def popup_view(request):
    """View for the popup/embedded version of the AI character"""
    return render(request, 'aicharacter/popup.html')

def your_view_function(request):
    logger.debug(f"ELEVEN_LABS_API_KEY: {settings.ELEVEN_LABS_API_KEY[:10]}...")  # Only log first 10 chars for security 