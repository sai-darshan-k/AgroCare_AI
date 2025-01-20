import os
import numpy as np
from tensorflow import lite
from tensorflow.keras.preprocessing.image import load_img, img_to_array
from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv
from datetime import datetime
import logging
import gdown  # To download the model from Google Drive
from langdetect import detect, DetectorFactory
from langdetect.lang_detect_exception import LangDetectException
from gtts import gTTS
from PIL import Image 
import time

# Ensure consistent language detection
DetectorFactory.seed = 0

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "your_secret_key")

# Configure logging
logging.basicConfig(level=logging.INFO)

# Google Drive link for the model
drive_link = "https://drive.google.com/file/d/1rFdr51QVWy3mpzWPCYgdRH1XCH7Yefv6"  # Model ID extracted
model_path = os.getenv("MODEL_PATH", "my_model.tflite")

# Function to download model from Google Drive
def download_model_from_drive(drive_link, destination):
    if not os.path.exists(destination):
        try:
            logging.info('Downloading model from Google Drive...')
            gdown.download(drive_link, destination, quiet=False)
            logging.info('Model downloaded successfully.')
        except Exception as e:
            logging.error(f"Error downloading model: {str(e)}")
            raise e

# Download and load the TensorFlow Lite model
download_model_from_drive(drive_link, model_path)

# Load the TensorFlow Lite model using the interpreter
interpreter = lite.Interpreter(model_path=model_path)
interpreter.allocate_tensors()

logging.info('Model loaded. Check http://127.0.0.1:5000/')

# Load the language model
groqllm = ChatGroq(model="llama3-8b-8192", temperature=0)
prompt = """(System: You are a crop assistant designed to give responses in the primary language as English. However, if the user asks a question in any language you should respond in the same language as the input. If the language is not one of these, the response will be in English. The system should detect the language of the input and provide a response accordingly. Do not repeat points and keep the response clear and concise.)

(user: Question: {question})"""
promptinstance = ChatPromptTemplate.from_template(prompt)

labels = {0: 'Healthy', 1: 'Powdery', 2: 'Rust'}
# Create a directory for storing the audio files if it doesn't exist
AUDIO_DIR = os.path.join(os.getcwd(), 'static', 'audio')
os.makedirs(AUDIO_DIR, exist_ok=True)

@app.route('/')
def index():
    return render_template('agrocare.html')

@app.route('/agrocare')
def agrocare():
    return render_template('agrocare.html')

@app.route('/speech')
def speech():
    return render_template('speech.html')

# Create a directory for storing the audio files if it doesn't exist
AUDIO_DIR = os.path.join(os.getcwd(), 'static', 'audio')
os.makedirs(AUDIO_DIR, exist_ok=True)

# Add a new route specifically for speech responses
@app.route('/ask_speech', methods=['POST'])
def ask_speech():
    question = request.json.get('question')
    logging.info(f"Received speech question: {question}")
    try:
        # Detect language and generate response
        detected_language = detect_language(question)
        response = promptinstance | groqllm | StrOutputParser()
        answer = response.invoke({'question': question})
        formatted_answer = format_answer(answer)

        # Generate audio only for speech interface
        audio_filename = generate_audio(formatted_answer.replace('<div style=\'text-align: left;\'>', '')
                                     .replace('</div>', '')
                                     .replace('<p>', '')
                                     .replace('</p>', ''), 
                                     detected_language)

        return jsonify({
            'answer': formatted_answer,
            'audio_url': f"/static/audio/{audio_filename}?t={int(time.time())}"
        })
    except Exception as e:
        logging.error(f"Error in speech response: {str(e)}")
        return jsonify({'answer': f'Error processing your request: {str(e)}'}), 500

# Modify the original ask route to handle text-only responses
@app.route('/ask', methods=['POST'])
def ask():
    question = request.json.get('question')
    logging.info(f"Received text question: {question}")
    try:
        # Generate text response only
        response = promptinstance | groqllm | StrOutputParser()
        answer = response.invoke({'question': question})
        formatted_answer = format_answer(answer)
        
        return jsonify({'answer': formatted_answer})
    except Exception as e:
        logging.error(f"Error in text response: {str(e)}")
        return jsonify({'answer': f'Error processing your request: {str(e)}'}), 500

def generate_audio(text, lang='en'):
    try:
        # Use a fixed filename
        audio_filename = "response.mp3"
        audio_path = os.path.join(AUDIO_DIR, audio_filename)
        
        # Generate audio file using gTTS
        tts = gTTS(text=text, lang=lang, slow=False)
        tts.save(audio_path)
        logging.info(f"Audio file generated: {audio_path}")
        return audio_filename
    except Exception as e:
        logging.error(f"Error generating audio: {str(e)}")
        return None

def detect_language(text):
    """
    Detect the language of the input text.
    """
    try:
        return detect(text)
    except LangDetectException:
        raise LangDetectException("Language detection failed.")

def format_answer(answer):
    """
    Format the response to include HTML tags for better display.
    """
    answer = answer.replace("**", "<strong>").replace("**", "</strong>")
    formatted_answer = "<div style='text-align: left;'>"
    lines = answer.split('\n')
    for line in lines:
        if line.strip():
            formatted_answer += f"<p>{line.strip()}</p>"
    formatted_answer += "</div>"
    return formatted_answer

@app.route('/predict', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({'prediction': 'No image uploaded'}), 400

    f = request.files['file']
    uploads_dir = os.path.join(os.path.dirname(__file__), 'uploads')
    os.makedirs(uploads_dir, exist_ok=True)

    file_path = os.path.join(uploads_dir, secure_filename(f.filename))
    f.save(file_path)
    try:
        predictions = getResult(file_path)
        predicted_label = labels[np.argmax(predictions)]
        return jsonify({'prediction': predicted_label})
    except Exception as e:
        logging.error(f"Error processing image: {str(e)}")
        return jsonify({'prediction': f'Error processing image: {str(e)}'}), 500

def getResult(image_path):
    """
    Process the uploaded image and predict the crop disease using TensorFlow Lite model.
    """
    # Load the image
    img = load_img(image_path, target_size=(225, 225))
    x = img_to_array(img)
    x = x.astype('float32') / 255.
    x = np.expand_dims(x, axis=0)

    # Set the input tensor
    input_details = interpreter.get_input_details()
    interpreter.set_tensor(input_details[0]['index'], x)

    # Run inference
    interpreter.invoke()

    # Get the output tensor
    output_details = interpreter.get_output_details()
    predictions = interpreter.get_tensor(output_details[0]['index'])[0]
    return predictions

@app.route('/weather')
def weather():
    return render_template('weather.html')

if __name__ == '__main__':
    # Render sets the PORT environment variable for the application
    port = int(os.environ.get("PORT", 5000))  # Default to 5000 if not set
    app.run(host="0.0.0.0", port=port, debug=True)

