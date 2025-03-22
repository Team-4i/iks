from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import os
from services.text_generation import TextGenerationService
from services.voice_service import VoiceService

print("Loading environment variables...")
load_dotenv()

# Validate required API keys
if not os.environ.get("GROQ_API_KEY"):
    raise ValueError("GROQ_API_KEY environment variable is not set")

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Initialize services
text_generation_service = TextGenerationService()
voice_service = VoiceService()

@app.route('/')
def chat():
    return render_template('index.html')

@app.route('/text-to-speech', methods=['POST'])
def text_to_speech():
    try:
        text = request.json.get('text', '')
        audio_base64, error = voice_service.text_to_speech(text)
        
        if error:
            return jsonify({"error": error}), 400 if "No text provided" in error else 500

        return jsonify({"audio": audio_base64})
            
    except Exception as e:
        import traceback
        print(f"Error in text-to-speech: {str(e)}")
        print(traceback.format_exc())
        return jsonify({
            "error": str(e),
            "stack_trace": traceback.format_exc()
        }), 500

@app.route('/get_response', methods=['POST'])
def get_response():
    user_input = request.form.get("user_input", "").strip()
    
    if user_input:
        response_text = text_generation_service.generate_response(user_input)
        return {"response": response_text}
    
    return {"response": "मुझे कोई इनपुट नहीं मिला। कृपय फिर स प्रयास करें।"}

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)

