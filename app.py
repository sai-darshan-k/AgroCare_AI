import os
import re
import numpy as np
import joblib
from tensorflow import lite
from flask import Flask, render_template, request, jsonify
import tensorflow as tf
from werkzeug.utils import secure_filename
import threading
import datetime
from PIL import Image
from tensorflow.keras.preprocessing.image import load_img, img_to_array
from flask import Flask, render_template, request, jsonify, flash, send_from_directory, session, redirect, url_for
from flask_babel import Babel, _
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv
from datetime import datetime
import logging
import requests
import feedparser
from nltk.sentiment import SentimentIntensityAnalyzer
import nltk
from urllib.parse import urlparse
import html
import pandas as pd
from bs4 import BeautifulSoup
from collections import OrderedDict
import gdown
from langdetect import detect, DetectorFactory
from langdetect.lang_detect_exception import LangDetectException
from apscheduler.schedulers.background import BackgroundScheduler
from gtts import gTTS
import time
import json
from flask_sqlalchemy import SQLAlchemy
from dateutil import parser
from translate import Translator

# Ensure consistent language detection
DetectorFactory.seed = 0

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "your_secret_key")
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///kissan_market.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize SQLAlchemy
db = SQLAlchemy(app)

# Configure logging
logging.basicConfig(level=logging.INFO)

def keep_alive():
    try:
        # Ping the public Render URL
        response = requests.get("https://agrocare-ai-v1vn.onrender.com/", timeout=5)
        logging.info(f"Keep-alive ping sent, status code: {response.status_code}")
    except Exception as e:
        logging.error(f"Keep-alive ping failed: {str(e)}")

# Initialize and start scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(keep_alive, 'interval', minutes=5)
scheduler.start()

# Google Drive link for the model
drive_link = "https://drive.google.com/file/d/1rFdr51QVWy3mpzWPCYgdRH1XCH7Yefv6"
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

labels = {0: 'Healthy', 1: 'Powdery', 2: 'Rust'}

# Download and load the TensorFlow Lite model
download_model_from_drive(drive_link, model_path)
interpreter = lite.Interpreter(model_path=model_path)
interpreter.allocate_tensors()

logging.info('Model loaded. Check http://127.0.0.1:5000/')

# Load the language model
groqllm = ChatGroq(model="llama3-8b-8192", temperature=0)
prompt = """(System: You are a crop assistant designed to give responses in English. The system receives questions in English (translated from the user's input language) and should provide clear, concise answers in English. Do not repeat points.)

(user: Question: {question})"""
promptinstance = ChatPromptTemplate.from_template(prompt)

# Prompt for speech (concise, 150 characters)
speech_prompt = """(System: You are a crop assistant designed to give responses in English. The system receives questions in English (translated from the user's input language) and should provide clear, concise answers in English, equal or limited to 500 characters. Do not repeat points.)

(user: Question: {question})"""
speech_promptinstance = ChatPromptTemplate.from_template(speech_prompt)

# Create a directory for storing the audio files
AUDIO_DIR = os.path.join(os.getcwd(), 'static', 'audio')
os.makedirs(AUDIO_DIR, exist_ok=True)

# Path to the Excel files
EXCEL_FILE_INSECTICIDES = "all_crops_insecticides_sheets.xlsx"
EXCEL_FILE_FUNGICIDES = "all_crops_fungicides_sheets.xlsx"
EXCEL_FILE_HERBICIDES = "all_herb_sheets.xlsx"
EXCEL_PGR = "all_pgr_sheets.xlsx"

# Define the expected column order
COLUMNS = [
    "Crop", "Pest(Disease)", "Pesticide", "a.i (gm)", "Formulation (gm/ml)", 
    "Dilution in Water (Liter)", "Waiting Period (in days)"
]
HERBICIDE_COLUMNS = [
    "Herbicide name & approved Crops", "Weed species", "Herbicide", "a.i (gm/Kg)", 
    "Formulati on in (gm/ ml /Kg/ ltr)", "Dilution in Water (Liter)", 
    "Waiting period/PHI between last application & harvest (days)"
]
PGR_COLUMNS = [
    "Name of PGR & approved Crops", "Time of application / purpose", 
    "Registered PLANT GROWTH REGULATORS (PGR)", "a.i (gm/Kg)", 
    "Formulati on in (gm/ ml /Kg/ ltr)", "Dilution in Water (Liter)", 
    "Waiting period/PHI between last application & harvest (days)"
]

# Database Models for Kissan E-Market
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    user_type = db.Column(db.String(10), nullable=False)  # 'farmer' or 'consumer'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    farm_name = db.Column(db.String(100))
    location = db.Column(db.String(200))
    phone = db.Column(db.String(15))
    
    def __repr__(self):
        return f'<User {self.username}>'

class Farmer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    farm_name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(15), nullable=False)
    description = db.Column(db.Text, nullable=True)
    products = db.Column(db.String(200), nullable=True)  # Comma-separated list of products
    
    def __repr__(self):
        return f'<Farmer {self.farm_name}>'

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    image_url = db.Column(db.String(200))
    farmer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Product {self.name}>'
    
class Cart(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    
    def __repr__(self):
        return f'<Cart Item {self.id}>'

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Order {self.id}>'

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    
    def __repr__(self):
        return f'<OrderItem {self.id}>'

# Routes
@app.route('/')
def index():
    return render_template('index.html')  # Root route to avoid 404

@app.route('/insecticides')
def insecticides():
    try:
        excel_data = pd.ExcelFile(EXCEL_FILE_INSECTICIDES)
        crops = excel_data.sheet_names
    except Exception as e:
        crops = []
        logging.error(f"Error loading insecticides Excel file: {e}")
    return render_template('insecticides.html', crops=crops)

@app.route('/fungicides')
def fungicides():
    try:
        excel_data = pd.ExcelFile(EXCEL_FILE_FUNGICIDES)
        crops = excel_data.sheet_names
    except Exception as e:
        crops = []
        logging.error(f"Error loading fungicides Excel file: {e}")
    return render_template('fungicides.html', crops=crops)

@app.route('/herbicides')
def herbicides():
    try:
        excel_data = pd.ExcelFile(EXCEL_FILE_HERBICIDES)
        crops = excel_data.sheet_names
    except Exception as e:
        crops = []
        logging.error(f"Error loading herbicides Excel file: {e}")
    return render_template('herbicides.html', crops=crops)

@app.route('/pgr')
def pgr():
    try:
        excel_data = pd.ExcelFile(EXCEL_PGR)
        crops = excel_data.sheet_names
    except Exception as e:
        crops = []
        logging.error(f"Error loading pgr Excel file: {e}")
    return render_template('pgr.html', crops=crops)

@app.route('/agrocare')
def agrocare():
    return render_template('agrocare.html')

@app.route('/speech')
def speech():
    return render_template('speech.html')

@app.route('/weather')
def weather():
    return render_template('weather.html')

@app.route('/maps')
def maps():
    return render_template('maps.html')

@app.route('/shc')
def shc():
    return render_template('shc.html')

@app.route('/schemes')
def schemes():
    return render_template('schemes.html')

@app.route('/fertilizer')
def fertilizer():
    return render_template('fertilizer.html')

def translate_long_text(text, translator, max_length=500):
    """Split text into chunks under max_length and translate each chunk."""
    if not text:
        return ""
    # Split text into sentences or chunks
    sentences = []
    current_chunk = ""
    for sentence in text.split('. '):  # Split by sentence
        if len(current_chunk) + len(sentence) + 2 <= max_length:
            current_chunk += sentence + ". " if sentence else ""
        else:
            if current_chunk:
                sentences.append(current_chunk.strip())
            current_chunk = sentence + ". " if sentence else ""
    if current_chunk:
        sentences.append(current_chunk.strip())
    
    # Translate each chunk
    translated_chunks = []
    for chunk in sentences:
        try:
            translated = translator.translate(chunk)
            translated_chunks.append(translated)
        except Exception as e:
            logging.error(f"Error translating chunk: {str(e)}")
            return f"Translation error: {str(e)}"
    return " ".join(translated_chunks)

def fetch_sensor_data():
    try:
        response = requests.get('https://iot-delta-vert.vercel.app/sensor-data', timeout=5)
        response.raise_for_status()
        data = response.json()
        logging.info(f"Fetched sensor data: {data}")
        return data
    except requests.RequestException as e:
        logging.error(f"Error fetching sensor data: {str(e)}")
        return {
            "temperature": None,
            "humidity": None,
            "rain_intensity": None,
            "rain_detected": None,
            "soil_moisture": None,
            "water_layer": None,
            "last_update": None
        }

# Add this function after existing imports and before any routes (e.g., after fetch_sensor_data)
def fetch_weather_forecast():
    try:
        api_key = "e10f65c590d431935edaaf55555c6146"
        lat, lon = 12.9716, 77.5946  # Bangalore coordinates
        url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={api_key}&units=metric"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        # Extract relevant forecast data (next 24 hours, simplified)
        forecast = []
        for entry in data['list'][:8]:  # Next 24 hours (3-hour intervals)
            dt = datetime.fromtimestamp(entry['dt']).strftime("%Y-%m-%d %H:%M")
            temp = entry['main']['temp']
            weather = entry['weather'][0]['description']
            forecast.append(f"{dt}: {temp}°C, {weather}")
        
        forecast_summary = f"Weather forecast for Bangalore: " + "; ".join(forecast)
        logging.info(f"Fetched weather forecast: {forecast_summary}")
        return forecast_summary
    except requests.RequestException as e:
        logging.error(f"Error fetching weather forecast: {str(e)}")
        return "No weather forecast available. Please try again later."

def fetch_weather_forecast():
    try:
        api_key = "e10f65c590d431935edaaf55555c6146"
        lat, lon = 12.9716, 77.5946  # Bangalore coordinates
        url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={api_key}&units=metric"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        # Extract relevant forecast data (next 24 hours, simplified)
        forecast = []
        for entry in data['list'][:8]:  # Next 24 hours (3-hour intervals)
            dt = datetime.fromtimestamp(entry['dt']).strftime("%Y-%m-%d %H:%M")
            temp = entry['main']['temp']
            weather = entry['weather'][0]['description']
            forecast.append(f"{dt}: {temp}°C, {weather}")
        
        forecast_summary = f"Weather forecast for Bangalore: " + "; ".join(forecast)
        logging.info(f"Fetched weather forecast: {forecast_summary}")
        return forecast_summary
    except requests.RequestException as e:
        logging.error(f"Error fetching weather forecast: {str(e)}")
        return "No weather forecast available. Please try again later."

@app.route('/ask_speech', methods=['POST'])
def ask_speech():
    data = request.json
    question = data.get('question')
    language = data.get('language', 'en-US')
    crop_type = data.get('crop_type', 'generic')
    logging.info(f"Received speech question: {question} in language: {language}, crop_type: {crop_type}")

    try:
        lang_map = {
            'en-US': 'en',
            'kn-IN': 'kn',
            'ta-IN': 'ta',
            'hi-IN': 'hi',
            'te-IN': 'te'
        }
        target_lang = lang_map.get(language, 'en')

        translator_to_en = Translator(to_lang='en', from_lang=target_lang)
        translator_to_target = Translator(to_lang=target_lang, from_lang='en')

        question_en = question
        if target_lang != 'en':
            try:
                question_en = translator_to_en.translate(question)
                logging.info(f"Translated question to English: {question_en}")
            except Exception as e:
                logging.error(f"Error translating question: {str(e)}")
                return jsonify({'answer': f'Error translating question: {str(e)}'}), 500

        # Fetch sensor and weather data
        sensor_data = fetch_sensor_data()
        weather_context = fetch_weather_forecast()

        if all(v is None for v in sensor_data.values()):
            sensor_context = "Sensor data unavailable. Check device connection."
            water_level = 0
            irrigation_advice = "Sensor data unavailable. Manually check soil moisture before watering."
        else:
            soil_moisture = sensor_data.get('soil_moisture', 0)
            soil_moisture = max(0, min(soil_moisture, 4095))  # clamp
            water_level = round(((4095 - soil_moisture) / 4095) * 100, 2)

            if water_level < 38.88:
                irrigation_advice = (
                    f"Water level is {water_level}%. Please water your plants to maintain soil moisture."
                )
            else:
                irrigation_advice = (
                    f"Water level is {water_level}%. No watering needed currently."
                )

            sensor_context = (
                f"Water Level: {water_level}%, "
                f"Water Layer: {sensor_data['water_layer'] or 'N/A'}, "
                f"Temperature: {sensor_data['temperature'] or 'N/A'}°C, "
                f"Humidity: {sensor_data['humidity'] or 'N/A'}%, "
                f"Rain Intensity: {sensor_data['rain_intensity'] or 'N/A'}, "
                f"Rain Detected: {sensor_data['rain_detected'] or 'N/A'}, "
                f"Last Update: {sensor_data['last_update'] or 'N/A'}. "
                f"{irrigation_advice}"
            )

        # Prepare prompt
        enhanced_speech_prompt = """
        (System: You are a crop assistant for {crop_type}. First, clearly and concisely answer the user's specific question. 
        If and only if the question relates to plant care, wilting, watering, or environmental concerns, then incorporate insights from sensor data ({sensor_context}) and weather forecast ({weather_context}). 
        Recommend watering only if water level is below 38.88%. 
        Keep responses under 500 characters and do not repeat content.)

        (user: Question: {question_en})
        """
        prompt = ChatPromptTemplate.from_template(enhanced_speech_prompt)

        response = prompt | groqllm | StrOutputParser()
        answer_en = response.invoke({
            'question_en': question_en,
            'crop_type': crop_type,
            'sensor_context': sensor_context,
            'weather_context': weather_context
        })

        answer_en = re.sub(r'[\*]+', '', answer_en)
        logging.info(f"Model response: {answer_en}")
        formatted_answer_en = format_answer(answer_en)

        # Translate if needed
        answer_translated = answer_en
        if target_lang != 'en':
            try:
                answer_translated = translate_long_text(answer_en, translator_to_target)
                if answer_translated.startswith("Translation error"):
                    raise Exception(answer_translated)
                logging.info(f"Translated to {target_lang}: {answer_translated}")
            except Exception as e:
                logging.error(f"Translation error: {str(e)}")
                return jsonify({'answer': f'Error translating response: {str(e)}'}), 500

        formatted_answer = format_answer(answer_translated)
        audio_filename = generate_audio(answer_translated, target_lang)
        if not audio_filename:
            return jsonify({'answer': 'Error generating audio'}), 500

        return jsonify({
            'answer': formatted_answer,
            'audio_url': f"/static/audio/{audio_filename}?t={int(time.time())}"
        })

    except Exception as e:
        logging.error(f"ask_speech error: {str(e)}")
        return jsonify({'answer': f'Error processing your request: {str(e)}'}), 500

@app.route('/ask', methods=['POST'])
def ask():
    question = request.json.get('question')
    logging.info(f"Received text question: {question}")
    try:
        response = promptinstance | groqllm | StrOutputParser()
        answer = response.invoke({'question': question})
        formatted_answer = format_answer(answer)
        return jsonify({'answer': formatted_answer})
    except Exception as e:
        logging.error(f"Error in text response: {str(e)}")
        return jsonify({'answer': f'Error processing your request: {str(e)}'}), 500

def strip_html_tags(text):
    """Remove HTML tags from text."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(text, "html.parser")
    return soup.get_text()

def generate_audio(text, lang='en'):
    try:
        # Strip HTML tags and clean text
        clean_text = strip_html_tags(text)
        # Remove Markdown formatting (asterisks, etc.)
        clean_text = re.sub(r'[\*]+', '', clean_text)  # Remove * or **
        clean_text = clean_text.strip()
        if not clean_text:
            logging.error("Cleaned text is empty after processing")
            return None
        logging.info(f"Generating audio for text: {clean_text} (lang: {lang})")
        audio_filename = f"response_{lang}_{int(time.time())}.mp3"  # Unique filename
        audio_path = os.path.join(AUDIO_DIR, audio_filename)
        
        # Delete all existing audio files in the AUDIO_DIR
        for existing_file in os.listdir(AUDIO_DIR):
            existing_file_path = os.path.join(AUDIO_DIR, existing_file)
            try:
                if os.path.isfile(existing_file_path) and existing_file.endswith('.mp3'):
                    os.remove(existing_file_path)
                    logging.info(f"Deleted existing audio file: {existing_file_path}")
            except Exception as e:
                logging.error(f"Error deleting existing audio file {existing_file_path}: {str(e)}")
        
        # Generate and save the new audio file
        tts = gTTS(text=clean_text, lang=lang, slow=False)
        tts.save(audio_path)
        logging.info(f"Audio file generated: {audio_path}")
        return audio_filename
    except Exception as e:
        logging.error(f"Error generating audio: {str(e)}")
        return None

def detect_language(text):
    try:
        return detect(text)
    except LangDetectException:
        raise LangDetectException("Language detection failed.")

def format_answer(answer):
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
    uploads_dir = os.path.join(os.path.dirname(__file__), 'Uploads')
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
    img = load_img(image_path, target_size=(225, 225))
    x = img_to_array(img)
    x = x.astype('float32') / 255.
    x = np.expand_dims(x, axis=0)
    input_details = interpreter.get_input_details()
    interpreter.set_tensor(input_details[0]['index'], x)
    interpreter.invoke()
    output_details = interpreter.get_output_details()
    predictions = interpreter.get_tensor(output_details[0]['index'])[0]
    return predictions

@app.route('/get_insecticides_data', methods=['POST'])
def get_insecticides_data():
    crop_name = request.form['crop_name']
    try:
        excel_data = pd.ExcelFile(EXCEL_FILE_INSECTICIDES)
        if crop_name in excel_data.sheet_names:
            crop_data = excel_data.parse(crop_name, header=None)
            crop_data = crop_data.iloc[:, :len(COLUMNS)]
            crop_data.columns = COLUMNS
            crop_data = crop_data[COLUMNS]
            crop_data = crop_data.fillna("")
            crop_data.insert(0, "Sl. No.", range(1, len(crop_data) + 1))
            crop_data_json = [OrderedDict(row) for _, row in crop_data.iterrows()]
            return jsonify({"columns": crop_data.columns.tolist(), "data": crop_data_json})
        else:
            return jsonify({"error": "Crop sheet not found."})
    except Exception as e:
        return jsonify({"error": f"Error reading data: {e}"})

@app.route('/get_fungicides_data', methods=['POST'])
def get_fungicides_data():
    crop_name = request.form['crop_name']
    try:
        excel_data = pd.ExcelFile(EXCEL_FILE_FUNGICIDES)
        if crop_name in excel_data.sheet_names:
            crop_data = excel_data.parse(crop_name, header=None)
            crop_data = crop_data.iloc[:, :len(COLUMNS)]
            crop_data.columns = COLUMNS
            crop_data = crop_data[COLUMNS]
            crop_data = crop_data.fillna("")
            crop_data.insert(0, "Sl. No.", range(1, len(crop_data) + 1))
            crop_data_json = [OrderedDict(row) for _, row in crop_data.iterrows()]
            return jsonify({"columns": crop_data.columns.tolist(), "data": crop_data_json})
        else:
            return jsonify({"error": "Crop sheet not found."})
    except Exception as e:
        return jsonify({"error": f"Error reading data: {e}"})

@app.route('/get_herbicides_data', methods=['POST'])
def get_herbicides_data():
    crop_name = request.form['crop_name']
    try:
        excel_data = pd.ExcelFile(EXCEL_FILE_HERBICIDES)
        if crop_name in excel_data.sheet_names:
            crop_data = excel_data.parse(crop_name, header=None)
            crop_data = crop_data.iloc[:, :len(HERBICIDE_COLUMNS)]
            crop_data.columns = HERBICIDE_COLUMNS
            crop_data = crop_data[HERBICIDE_COLUMNS]
            crop_data = crop_data.fillna("")
            crop_data.insert(0, "Sl. No.", range(1, len(crop_data) + 1))
            crop_data_json = [OrderedDict(row) for _, row in crop_data.iterrows()]
            return jsonify({"columns": crop_data.columns.tolist(), "data": crop_data_json})
        else:
            return jsonify({"error": "Crop sheet not found."})
    except Exception as e:
        logging.error(f"Error reading herbicide data: {e}")
        return jsonify({"error": f"Error reading data: {e}"})

@app.route('/get_pgr_data', methods=['POST'])
def get_pgr_data():
    crop_name = request.form['crop_name']
    try:
        excel_data = pd.ExcelFile(EXCEL_PGR)
        if crop_name in excel_data.sheet_names:
            crop_data = excel_data.parse(crop_name, header=None)
            crop_data = crop_data.iloc[:, :len(PGR_COLUMNS)]
            crop_data.columns = PGR_COLUMNS
            crop_data = crop_data[PGR_COLUMNS]
            crop_data = crop_data.fillna("")
            crop_data.insert(0, "Sl. No.", range(1, len(crop_data) + 1))
            crop_data_json = [OrderedDict(row) for _, row in crop_data.iterrows()]
            return jsonify({"columns": crop_data.columns.tolist(), "data": crop_data_json})
        else:
            return jsonify({"error": "Crop sheet not found."})
    except Exception as e:
        logging.error(f"Error reading pgr data: {e}")
        return jsonify({"error": f"Error reading data: {e}"})

# Soil Implementation
excel_file = "Soil_Labs_By_State1.xlsx"
df_all_sheets = pd.read_excel(excel_file, sheet_name=None)

@app.route('/soil_labs')
def soil_labs():
    df_combined = pd.concat(df_all_sheets.values(), ignore_index=True)
    states = df_combined['State'].dropna().unique().tolist()
    return render_template("soil_labs.html", states=states)

@app.route("/get_districts", methods=["GET"])
def get_districts():
    state = request.args.get("state")
    if state:
        df_combined = pd.concat(df_all_sheets.values(), ignore_index=True)
        df_combined['State'] = df_combined['State'].str.replace('&', 'and').str.strip()
        state_clean = state.replace('&', 'and').strip()
        districts = df_combined[df_combined['State'] == state_clean]['District'].dropna().unique().tolist()
        return jsonify(districts)
    return jsonify([])

@app.route("/get_data", methods=["GET"])
def get_data():
    state = request.args.get("state")
    district = request.args.get("district")
    if state and district:
        df_combined = pd.concat(df_all_sheets.values(), ignore_index=True)
        data_filtered = df_combined[(df_combined['State'] == state) & (df_combined['District'] == district)]
        if data_filtered.empty:
            return jsonify([])
        return jsonify(data_filtered.to_dict(orient="records"))
    return jsonify([])

# Karnataka Market Data
URLS = {
    "Egg Prices": "https://daatacenter.com/trade/today-egg-rate-bangalore/",
    "Chicken Rates": "https://daatacenter.com/chicken-rate/chicken-rate-today-in-bangalore/",
    "Vegetable Prices": "https://vegetablemarketprice.com/market/karnataka/today",
    "Petrol Prices": "https://www.ndtv.com/fuel-prices/petrol-price-in-bangalore-city",
    "Diesel Prices": "https://www.ndtv.com/fuel-prices/diesel-price-in-bangalore-city",
    "Fruit Prices": "https://market.todaypricerates.com/Karnataka-fruits-price",
    "Flower Rates": "https://daatacenter.com/flowers-price/today-flower-rate-in-bangalore-market/",
}

def scrape_table(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        if "ndtv.com" in url:
            div = soup.find("div", id="myID")
            if div:
                rows = div.find_all("tr")
                if rows:
                    headers_row = rows[0]
                    table_headers = [cell.text.strip() for cell in headers_row.find_all(["th", "td"])]
                    if "Change" in table_headers:
                        change_index = table_headers.index("Change")
                        table_headers.pop(change_index)
                    else:
                        change_index = None
                    table_rows = []
                    for row in rows[1:]:
                        cells = [cell.text.strip() for cell in row.find_all(["td", "th"])]
                        if change_index is not None and len(cells) > change_index:
                            cells.pop(change_index)
                        if any(cells):
                            table_rows.append(cells)
                    return table_headers, table_rows
                return "No table-like rows found in the div with id='myID'.", []
            return "No div with id='myID' found on the webpage.", []
        table = soup.find("table")
        if table:
            headers_row = table.find("tr")
            table_headers = [cell.text.strip() for cell in headers_row.find_all(["th", "td"])]
            table_rows = []
            for row in table.find_all("tr")[1:]:
                cells = [cell.text.strip() for cell in row.find_all(["td", "th"])]
                if any(cells):
                    table_rows.append(cells)
            return table_headers, table_rows
        return "No table found on the webpage.", []
    except requests.RequestException as e:
        return f"Failed to retrieve data: {str(e)}", []

@app.route('/market', methods=["GET", "POST"])
def market():
    selected_category = None
    table_headers = []
    table_rows = []
    error_message = None
    if request.method == "POST":
        selected_category = request.form.get("category")
        if selected_category in URLS:
            url = URLS[selected_category]
            result = scrape_table(url)
            if isinstance(result[0], str):
                error_message = result[0]
            else:
                table_headers, table_rows = result
    return render_template(
        "market.html",
        categories=URLS.keys(),
        selected_category=selected_category,
        table_headers=table_headers,
        table_rows=table_rows,
        error_message=error_message,
    )

# News Module
nltk.data.path.append(os.path.join(os.path.dirname(__file__), "nltk_data"))
nltk.download('vader_lexicon', download_dir=nltk.data.path[0])

RSS_FEEDS = {
    "india": "https://feeds.feedburner.com/ndtvnews-india-news",
    "world": "https://feeds.feedburner.com/ndtvnews-world-news",
    "education": {"The Hindu Education": "https://www.thehindu.com/education/feeder/default.rss"},
    "agriculture": {"The Hindu Agriculture": "https://www.thehindu.com/sci-tech/agriculture/feeder/default.rss"},
    "health": "https://www.thehindu.com/sci-tech/health/feeder/default.rss",
    "sports": "https://www.thehindu.com/sport/feeder/default.rss",
    "economy": "https://www.thehindu.com/business/Economy/feeder/default.rss"
}

sia = SentimentIntensityAnalyzer()

def clean_html_content(text):
    text = html.unescape(text)
    for tag in ['<p>', '</p>', '<br>', '<br/>', '<br />', '<div>', '</div>']:
        text = text.replace(tag, ' ')
    return text.strip()

def analyze_sentiment(text):
    score = sia.polarity_scores(text)['compound']
    if score >= 0.05:
        return "Positive 😊"
    elif score <= -0.05:
        return "Negative 😞"
    else:
        return "Neutral 😐"

def validate_feed_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False

def fetch_feed(url, source_name=""):
    if not validate_feed_url(url):
        logging.error(f"Invalid URL format for {source_name}: {url}")
        return None
    try:
        feed = feedparser.parse(url)
        if feed.bozo:
            logging.error(f"Feed parsing error for {source_name}: {feed.bozo_exception}")
            return None
        return feed
    except Exception as e:
        logging.error(f"Error fetching feed from {source_name}: {str(e)}")
        return None

def process_feed_entry(entry, source_name=""):
    try:
        image_url = None
        if hasattr(entry, 'media_content') and entry.media_content:
            image_url = entry.media_content[0].get("url")
        elif hasattr(entry, 'links'):
            for link in entry.links:
                if link.get('type', '').startswith('image'):
                    image_url = link.get('href')
                    break
        summary = entry.get('summary', entry.get('description', ''))
        summary = clean_html_content(summary)
        published = entry.get('published', entry.get('updated', 'No date'))
        return {
            "source": source_name,
            "title": entry.get('title', 'No title'),
            "link": entry.get('link', '#'),
            "published": published,
            "summary": summary,
            "image": image_url,
            "sentiment": analyze_sentiment(summary)
        }
    except Exception as e:
        logging.error(f"Error processing entry from {source_name}: {str(e)}")
        return None

@app.route('/news', methods=["GET", "POST"])
def news():
    category = request.form.get('category', 'india')
    articles = []
    if category in ['education', 'agriculture']:
        for source_name, url in RSS_FEEDS[category].items():
            feed = fetch_feed(url, source_name)
            if feed:
                for entry in feed.entries:
                    article = process_feed_entry(entry, source_name)
                    if article:
                        articles.append(article)
    else:
        feed = fetch_feed(RSS_FEEDS.get(category, ""))
        if feed:
            for entry in feed.entries:
                article = process_feed_entry(entry, category)
                if article:
                    articles.append(article)
    if not articles:
        flash(f"No articles found for {category} category.", "warning")
    def get_published_date(article):
        try:
            return parser.parse(article['published'])
        except (ValueError, TypeError):
            return None
    articles = sorted([a for a in articles if get_published_date(a) is not None], 
                      key=get_published_date, reverse=True)
    return render_template('news.html', articles=articles, category=category)

# Mandi Data
API_URL = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
API_KEY = "579b464db66ec23bdd000001eca496d3a4724af148b12338926e92c3"

def fetch_all_states():
    params = {'api-key': API_KEY, 'format': 'json', 'limit': 12000}
    response = requests.get(API_URL, params=params)
    states = []
    if response.status_code == 200:
        records = response.json().get('records', [])
        states = sorted(set(record.get('state', '') for record in records if record.get('state')))
    return states

@app.route('/mandi')
def mandi():
    states = fetch_all_states()
    return render_template('mandi.html', states=states, districts=[], data=[])

@app.route('/districts', methods=['POST'])
def districts():
    state = request.json.get('state')
    params = {'api-key': API_KEY, 'format': 'json', 'limit': 12000, 'filters[state.keyword]': state}
    response = requests.get(API_URL, params=params)
    districts = []
    if response.status_code == 200:
        records = response.json().get('records', [])
        districts = sorted(set(record.get('district', '') for record in records if record.get('district')))
    return jsonify(districts)

@app.route('/data', methods=['POST'])
def data():
    state = request.form.get('state')
    district = request.form.get('district')
    params = {
        'api-key': API_KEY,
        'format': 'json',
        'limit': 12000,
        'filters[state.keyword]': state,
        'filters[district]': district
    }
    response = requests.get(API_URL, params=params)
    data = []
    if response.status_code == 200:
        data = response.json().get('records', [])
    states = fetch_all_states()
    return render_template('mandi.html', states=states, selected_state=state, data=data)

# Fertilizer Prediction
clf = joblib.load("fertilizer_prediction_model.pkl")
label_encoders = joblib.load("label_encoders.pkl")

@app.route('/fertilizers', methods=['POST'])
def fertilizers():
    try:
        user_data = {
            "Temparature": float(request.form['temperature']),
            "Humidity": float(request.form['humidity']),
            "Moisture": float(request.form['moisture']),
            "Soil Type": request.form['soil_type'],
            "Crop Type": request.form['crop_type'],
            "Nitrogen": int(request.form['nitrogen']),
            "Potassium": int(request.form['potassium']),
            "Phosphorous": int(request.form['phosphorous'])
        }
        for col in ["Soil Type", "Crop Type"]:
            if user_data[col] in label_encoders[col].classes_:
                user_data[col] = label_encoders[col].transform([user_data[col]])[0]
            else:
                return jsonify({"error": f"Invalid input for {col}. Please enter a valid category."})
        user_df = pd.DataFrame([user_data])
        prediction = clf.predict(user_df)
        predicted_fertilizer = label_encoders["Fertilizer Name"].inverse_transform(prediction)[0]
        return jsonify({"prediction": predicted_fertilizer})
    except Exception as e:
        return jsonify({"error": str(e)})

# Kissan E-Market Routes
@app.route('/emarket')
def home():
    if 'user_id' not in session:
        flash('Please login to access this page', 'error')
        return render_template('emarket.html', products=Product.query.limit(8).all(), show_login=True)
    user = User.query.get(session['user_id'])
    products = Product.query.limit(8).all()
    return render_template('emarket.html', products=products, username=user.username)

@app.route('/products.html')
def redirect_products_html():
    return redirect(url_for('products'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        user_type = request.form.get('user_type')
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('register.html', user_type=user_type)

        if User.query.filter_by(username=username).first() or User.query.filter_by(email=email).first():
            flash('Username or email already exists', 'error')
            return render_template('register.html', user_type=user_type)

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, email=email, password=hashed_password, user_type=user_type)
        db.session.add(new_user)
        db.session.commit()

        if user_type == 'farmer':
            farm_name = request.form.get('farm_name')
            location = request.form.get('location')
            phone = request.form.get('phone')
            description = request.form.get('description')
            products = request.form.getlist('products')
            farmer = Farmer(user_id=new_user.id, farm_name=farm_name, location=location, phone=phone, description=description, products=','.join(products))
            db.session.add(farmer)
            db.session.commit()

        return render_template('register.html', user_type=user_type, registration_success=True)

    user_type = request.args.get('type', 'consumer')
    return render_template('register.html', user_type=user_type)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        if not (username or email):
            flash('Please provide either a username or email', 'error')
            return render_template('emarket.html', products=Product.query.limit(8).all(), login_error='Please provide either a username or email', show_login=True)

        if username:
            user = User.query.filter_by(username=username).first()
        else:
            user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['user_type'] = user.user_type
            flash('Login successful!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid username/email or password', 'error')
            return render_template('emarket.html', products=Product.query.limit(8).all(), login_error='Invalid username/email or password', show_login=True)

    return redirect(url_for('home'))

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('user_type', None)
    flash('You have been logged out')
    return redirect(url_for('home'))

@app.route('/farmer/dashboard')
def farmer_dashboard():
    if 'user_id' not in session or session['user_type'] != 'farmer':
        flash('Please login as a farmer to access this page')
        return redirect(url_for('login'))
    farmer_id = session['user_id']
    products = Product.query.filter_by(farmer_id=farmer_id).all()
    return render_template('farmer_dashboard.html', products=products)

@app.route('/farmer/add_product', methods=['GET', 'POST'])
def add_product():
    if 'user_id' not in session or session['user_type'] != 'farmer':
        flash('Please login as a farmer to access this page')
        return redirect(url_for('login'))
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        price = float(request.form.get('price'))
        quantity = int(request.form.get('quantity'))
        category = request.form.get('category')
        image_url = request.form.get('image_url')
        new_product = Product(
            name=name,
            description=description,
            price=price,
            quantity=quantity,
            category=category,
            image_url=image_url,
            farmer_id=session['user_id']
        )
        db.session.add(new_product)
        db.session.commit()
        flash('Product added successfully')
        return redirect(url_for('farmer_dashboard'))
    return render_template('add_product.html')

@app.route('/products')
def products():
    category = request.args.get('category')
    if category:
        products = Product.query.filter_by(category=category).all()
    else:
        products = Product.query.all()
    return render_template('products.html', products=products)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    farmer = User.query.get(product.farmer_id)
    return render_template('product_detail.html', product=product, farmer=farmer)

@app.route('/add_to_cart/<int:product_id>')
def add_to_cart(product_id):
    if 'user_id' not in session:
        flash('Please login to add items to cart')
        return redirect(url_for('login'))
    cart_item = Cart.query.filter_by(user_id=session['user_id'], product_id=product_id).first()
    if cart_item:
        cart_item.quantity += 1
    else:
        new_cart_item = Cart(
            user_id=session['user_id'],
            product_id=product_id,
            quantity=1
        )
        db.session.add(new_cart_item)
    db.session.commit()
    flash('Item added to cart')
    return redirect(url_for('cart'))

@app.route('/cart')
def cart():
    if 'user_id' not in session:
        flash('Please login to view your cart')
        return redirect(url_for('login'))
    cart_items = Cart.query.filter_by(user_id=session['user_id']).all()
    total = 0
    cart_products = []
    for item in cart_items:
        product = Product.query.get(item.product_id)
        total += product.price * item.quantity
        cart_products.append({
            'cart_id': item.id,
            'product': product,
            'quantity': item.quantity
        })
    return render_template('cart.html', cart_products=cart_products, total=total)

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if 'user_id' not in session:
        flash('Please login to checkout')
        return redirect(url_for('login'))
    if request.method == 'POST':
        cart_items = Cart.query.filter_by(user_id=session['user_id']).all()
        if not cart_items:
            flash('Your cart is empty')
            return redirect(url_for('cart'))
        total = 0
        for item in cart_items:
            product = Product.query.get(item.product_id)
            total += product.price * item.quantity
        new_order = Order(
            user_id=session['user_id'],
            total_amount=total,
            status='pending'
        )
        db.session.add(new_order)
        db.session.flush()
        for item in cart_items:
            product = Product.query.get(item.product_id)
            order_item = OrderItem(
                order_id=new_order.id,
                product_id=item.product_id,
                quantity=item.quantity,
                price=product.price
            )
            db.session.add(order_item)
            product.quantity -= item.quantity
            db.session.delete(item)
        db.session.commit()
        flash('Order placed successfully')
        return redirect(url_for('orders'))
    return render_template('checkout.html')

@app.route('/orders')
def orders():
    if 'user_id' not in session:
        flash('Please login to view your orders')
        return redirect(url_for('login'))
    orders = Order.query.filter_by(user_id=session['user_id']).order_by(Order.created_at.desc()).all()
    return render_template('orders.html', orders=orders)

@app.route('/order/<int:order_id>')
def order_detail(order_id):
    if 'user_id' not in session:
        flash('Please login to view order details')
        return redirect(url_for('orders'))
    order = Order.query.get_or_404(order_id)
    if order.user_id != session['user_id'] and session['user_type'] != 'farmer':
        flash('You do not have permission to view this order')
        return redirect(url_for('orders'))
    order_items = OrderItem.query.filter_by(order_id=order.id).all()
    items = []
    for item in order_items:
        product = Product.query.get(item.product_id)
        items.append({
            'product': product,
            'quantity': item.quantity,
            'price': item.price
        })
    return render_template('order_detail.html', order=order, items=items)

# Disease Diagnosis
app.config['UPLOAD_FOLDER'] = 'Uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg'}

# Create upload folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Define image size
IMG_SIZE = (256, 256)

# Load the TFLite model
model_path = 'model_quantized.tflite'
interpreter = tf.lite.Interpreter(model_path=model_path)
interpreter.allocate_tensors()

# Get input and output details
input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()

# Log model input details for debugging
print("Input details:", input_details)
print("Output details:", output_details)

# Original class names
original_class_names = [
    "Apple___Apple_scab", "Apple___Black_rot", "Apple___Cedar_apple_rust", "Apple___healthy",
    "Blueberry___healthy", "Cherry___Powdery_mildew", "Cherry___healthy", "Corn___Cercospora_leaf_spot Gray_leaf_spot",
    "Corn___Common_rust", "Corn___Northern_Leaf_Blight", "Corn___healthy", "Grape___Black_rot",
    "Grape___Esca_(Black_Measles)", "Grape___Leaf_blight_(Isariopsis_Leaf_Spot)", "Grape___healthy",
    "Orange___Haunglongbing_(Citrus_greening)", "Peach___Bacterial_spot", "Peach___healthy",
    "Pepper,_bell___Bacterial_spot", "Pepper,_bell___healthy", "Potato___Early_blight", "Potato___Late_blight",
    "Potato___healthy", "Raspberry___healthy", "Soybean___healthy", "Squash___Powdery_mildew",
    "Strawberry___Leaf_scorch", "Strawberry___healthy", "Tomato___Bacterial_spot", "Tomato___Early_blight",
    "Tomato___Late_blight", "Tomato___Leaf_Mold", "Tomato___Septoria_leaf_spot", "Tomato___Spider_mites Two-spotted_spider_mite",
    "Tomato___Target_Spot", "Tomato___Tomato_Yellow_Leaf_Curl_Virus", "Tomato___Tomato_mosaic_virus", "Tomato___healthy"
]

# Disease information dictionary
disease_info = {
    "Apple_scab": {
        "disease_name": "Apple Scab",
        "symptoms": "Dark, velvety spots on leaves and fruit, leaf drop, deformed fruit.",
        "organic_cure": "Apply neem oil, remove infected leaves, improve air circulation.",
        "prevention_tips": "Prune trees for better airflow, avoid overhead watering, use resistant varieties.",
        "seasonal_risk": "Spring and early summer, especially in wet conditions."
    },
    "Black_rot": {
        "disease_name": "Black Rot",
        "symptoms": "Black spots on leaves and fruit, yellowing leaves, fruit rot.",
        "organic_cure": "Use copper-based fungicides, prune affected areas, maintain hygiene.",
        "prevention_tips": "Remove fallen leaves, apply mulch, sanitize tools.",
        "seasonal_risk": "Late spring to summer, humid weather."
    },
    "Cedar_apple_rust": {
        "disease_name": "Cedar Apple Rust",
        "symptoms": "Yellow-orange spots on leaves, galls on twigs, reduced fruit quality.",
        "organic_cure": "Remove nearby cedar trees, apply sulfur spray, prune infected parts.",
        "prevention_tips": "Plant resistant varieties, maintain distance from cedar trees.",
        "seasonal_risk": "Spring, during wet and warm weather."
    },
    "healthy": {
        "disease_name": "Healthy",
        "symptoms": "No visible symptoms, normal growth and appearance.",
        "organic_cure": "Maintain good watering and nutrient practices to keep plants healthy.",
        "prevention_tips": "Regular monitoring, balanced fertilization, proper irrigation.",
        "seasonal_risk": "Not applicable."
    },
    "Powdery_mildew": {
        "disease_name": "Powdery Mildew",
        "symptoms": "White powdery spots on leaves, stunted growth, leaf curling.",
        "organic_cure": "Spray with milk solution (1:9 milk:water), improve air flow, use neem oil.",
        "prevention_tips": "Avoid overcrowding, prune for ventilation, water at the base.",
        "seasonal_risk": "Summer, in warm and dry conditions."
    },
    "Cercospora_leaf_spot Gray_leaf_spot": {
        "disease_name": "Cercospora Leaf Spot/Gray Leaf Spot",
        "symptoms": "Gray-white spots with dark borders on leaves, leaf yellowing.",
        "organic_cure": "Remove infected leaves, apply compost tea, ensure proper spacing.",
        "prevention_tips": "Crop rotation, remove plant debris, use resistant hybrids.",
        "seasonal_risk": "Summer, in warm and humid conditions."
    },
    "Common_rust": {
        "disease_name": "Common Rust",
        "symptoms": "Orange-brown spots on leaves, reduced photosynthesis.",
        "organic_cure": "Use sulfur dust, improve ventilation, remove affected leaves.",
        "prevention_tips": "Plant resistant varieties, avoid dense planting.",
        "seasonal_risk": "Summer, during warm and wet weather."
    },
    "Northern_Leaf_Blight": {
        "disease_name": "Northern Leaf Blight",
        "symptoms": "Long, gray-green lesions on leaves, leaf death.",
        "organic_cure": "Crop rotation, remove debris, apply garlic extract.",
        "prevention_tips": "Use resistant hybrids, space plants properly, avoid overhead irrigation.",
        "seasonal_risk": "Late summer, in cool and wet conditions."
    },
    "Esca_(Black_Measles)": {
        "disease_name": "Esca (Black Measles)",
        "symptoms": "Dark streaks on wood, leaf discoloration, fruit shriveling.",
        "organic_cure": "Prune infected parts, apply biochar, avoid water stress.",
        "prevention_tips": "Maintain plant health, avoid wounding, use organic mulch.",
        "seasonal_risk": "Summer, in warm climates."
    },
    "Leaf_blight_(Isariopsis_Leaf_Spot)": {
        "disease_name": "Leaf Blight (Isariopsis Leaf Spot)",
        "symptoms": "Dark spots on leaves, premature leaf drop.",
        "organic_cure": "Use copper spray, remove infected leaves, improve drainage.",
        "prevention_tips": "Prune for airflow, avoid wet foliage, monitor plant stress.",
        "seasonal_risk": "Late spring to summer, in humid conditions."
    },
    "Haunglongbing_(Citrus_greening)": {
        "disease_name": "Huanglongbing (Citrus Greening)",
        "symptoms": "Yellowing leaves, misshapen fruit, bitter taste.",
        "organic_cure": "No cure; remove infected trees, use resistant varieties, control psyllids with neem.",
        "prevention_tips": "Monitor for psyllids, use healthy planting material, apply organic insecticides.",
        "seasonal_risk": "Year-round in warm climates."
    },
    "Bacterial_spot": {
        "disease_name": "Bacterial Spot",
        "symptoms": "Water-soaked spots turning dark brown/black, leaf drop.",
        "organic_cure": "Apply copper-based sprays, remove affected parts, avoid overhead watering.",
        "prevention_tips": "Use disease-free seeds, rotate crops, maintain dry foliage.",
        "seasonal_risk": "Summer, in warm and wet conditions."
    },
    "Early_blight": {
        "disease_name": "Early Blight",
        "symptoms": "Concentric rings on leaves, yellowing, leaf drop.",
        "organic_cure": "Use baking soda spray, mulch soil, rotate crops.",
        "prevention_tips": "Stake plants, remove lower leaves, avoid wet conditions.",
        "seasonal_risk": "Early summer, in warm and humid weather."
    },
    "Late_blight": {
        "disease_name": "Late Blight",
        "symptoms": "Dark, water-soaked spots on leaves, white mold, rapid decay.",
        "organic_cure": "Apply copper fungicide, remove infected plants, improve air circulation.",
        "prevention_tips": "Use resistant varieties, avoid overhead watering, monitor weather.",
        "seasonal_risk": "Late summer, in cool and wet conditions."
    },
    "Leaf_scorch": {
        "disease_name": "Leaf Scorch",
        "symptoms": "Brown, scorched leaf edges, leaf drop.",
        "organic_cure": "Ensure proper watering, mulch, apply compost tea.",
        "prevention_tips": "Maintain soil moisture, avoid drought stress, use mulch.",
        "seasonal_risk": "Summer, during hot and dry periods."
    },
    "Leaf_Mold": {
        "disease_name": "Leaf Mold",
        "symptoms": "Yellowing leaves with grayish-white mold underneath.",
        "organic_cure": "Increase ventilation, apply sulfur spray, remove affected leaves.",
        "prevention_tips": "Prune for airflow, avoid high humidity, stake plants.",
        "seasonal_risk": "Summer, in warm and humid conditions."
    },
    "Septoria_leaf_spot": {
        "disease_name": "Septoria Leaf Spot",
        "symptoms": "Small, water-soaked spots turning gray with black dots.",
        "organic_cure": "Remove infected leaves, use neem oil, avoid wet foliage.",
        "prevention_tips": "Rotate crops, mulch soil, water at the base.",
        "seasonal_risk": "Late summer, in wet conditions."
    },
    "Spider_mites Two-spotted_spider_mite": {
        "disease_name": "Spider Mites (Two-Spotted)",
        "symptoms": "Tiny yellow spots on leaves, webbing, leaf drop.",
        "organic_cure": "Spray with water, use insecticidal soap, introduce predatory mites.",
        "prevention_tips": "Maintain humidity, monitor plants, avoid dust buildup.",
        "seasonal_risk": "Summer, in hot and dry conditions."
    },
    "Target_Spot": {
        "disease_name": "Target Spot",
        "symptoms": "Concentric rings on leaves, yellowing, defoliation.",
        "organic_cure": "Remove debris, apply compost tea, improve spacing.",
        "prevention_tips": "Stake plants, avoid wet leaves, remove lower foliage.",
        "seasonal_risk": "Summer, in warm and humid weather."
    },
    "Tomato_Yellow_Leaf_Curl_Virus": {
        "disease_name": "Yellow Leaf Curl Virus",
        "symptoms": "Yellowing, curling leaves, stunted growth.",
        "organic_cure": "Remove infected plants, control whiteflies with neem, use reflective mulch.",
        "prevention_tips": "Use row covers, monitor whiteflies, plant resistant varieties.",
        "seasonal_risk": "Summer, in warm climates."
    },
    "Tomato_mosaic_virus": {
        "disease_name": "Mosaic Virus",
        "symptoms": "Mottled leaves, yellowing, distorted growth.",
        "organic_cure": "Remove infected plants, disinfect tools, avoid handling wet plants.",
        "prevention_tips": "Use virus-free seeds, avoid tobacco use near plants, rotate crops.",
        "seasonal_risk": "Year-round, higher in warm weather."
    }
}

def allowed_file(filename):
    """Check if the file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def get_modified_class_name(original_name):
    """Strip crop prefix from class name"""
    return original_name.split("___")[-1].replace(",_", "_")

def preprocess_image(image_file):
    """Preprocess image for prediction"""
    try:
        img = Image.open(image_file).convert('RGB')  # Ensure RGB format
        img = img.resize(IMG_SIZE)
        img_array = np.array(img, dtype=np.float32)  # Explicitly set to float32
        img_array = np.expand_dims(img_array, 0)     # Add batch dimension
        img_array = img_array / 255.0                # Rescale to [0, 1]
        return img_array
    except Exception as e:
        raise ValueError(f"Image preprocessing failed: {str(e)}")

def predict_disease(image_file):
    """Make prediction using TFLite model"""
    try:
        input_data = preprocess_image(image_file)
        
        print("Input shape:", input_data.shape)
        print("Input dtype:", input_data.dtype)
        
        interpreter.set_tensor(input_details[0]['index'], input_data)
        interpreter.invoke()
        output_data = interpreter.get_tensor(output_details[0]['index'])
        
        print("Raw output:", output_data[0])
        
        predicted_class = np.argmax(output_data[0])
        confidence = float(np.max(output_data[0]))
        
        original_predicted_name = original_class_names[predicted_class]
        modified_predicted_name = get_modified_class_name(original_predicted_name)
        disease_details = disease_info.get(modified_predicted_name, {})
        
        return {
            "disease_name": disease_details.get("disease_name", "Unknown"),
            "confidence": confidence,
            "symptoms": disease_details.get("symptoms", "No information available"),
            "organic_cure": disease_details.get("organic_cure", "No information available"),
            "prevention_tips": disease_details.get("prevention_tips", "No information available"),
            "seasonal_risk": disease_details.get("seasonal_risk", "No information available")
        }
    except Exception as e:
        raise ValueError(f"Prediction failed: {str(e)}")

@app.route('/leaf-diagnosis')
def leaf_diagnosis():
    """Render the leaf diagnosis page"""
    return render_template('leaf_diagnosis.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload and prediction"""
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        try:
            result = predict_disease(file_path)
            return jsonify({
                "success": True,
                "filename": filename,
                "result": result
            })
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            return jsonify({"error": "An unexpected error occurred"}), 500
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)
    
    return jsonify({"error": "File type not allowed"}), 400

# Sensor Dashboard
sensor_data = {
    "temperature": None,
    "humidity": None,
    "rain_intensity": None,
    "rain_detected": None,
    "soil_moisture": None,
    "water_layer": None,
    "last_update": None
}

data_lock = threading.Lock()

@app.route('/sensor-data', methods=['POST', 'GET'])
def update_sensor_data():
    global sensor_data
    if request.method == 'POST':
        if request.is_json:
            with data_lock:
                data = request.get_json()
                sensor_data.update(data)
                sensor_data["last_update"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return jsonify({"message": "Data updated", "timestamp": sensor_data["last_update"]}), 200
        return jsonify({"error": "Invalid JSON"}), 400
    elif request.method == 'GET':
        with data_lock:
            return jsonify(sensor_data), 200

@app.route('/sensor-dashboard')
def sensor_dashboard():
    """Render the sensor dashboard page"""
    return render_template('sensor_dashboard.html')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create database tables
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)