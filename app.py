import os
import numpy as np
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing.image import load_img, img_to_array
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, session
from werkzeug.utils import secure_filename
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv
import logging
import requests  # For weather API integration

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "your_secret_key")

# Configure logging
logging.basicConfig(level=logging.INFO)

# Directly set the path to the model
model_path = os.getenv("MODEL_PATH", "my_model.keras")

# Load the model
model = load_model(model_path)
logging.info('Model loaded. Check http://127.0.0.1:5000/')

# Load the language model
groqllm = ChatGroq(model="llama3-8b-8192", temperature=0)
prompt = """(system: You are a crop assistant specializing in agriculture. If the user's question is related to agriculture, provide a detailed and helpful response. If the question is unrelated to agriculture, respond with "I'm sorry, I can only assist with agriculture-related queries.")
(user: Question: {question})"""
promptinstance = ChatPromptTemplate.from_template(prompt)

# Labels for image classification
labels = {0: 'Healthy', 1: 'Powdery', 2: 'Rust'}

@app.route('/agrocare')
def agrocare():
    return render_template('agrocare.html')

@app.route('/')
def index():
    return redirect(url_for('agrocare'))

@app.route('/speech')
def speech():
    return render_template('speech.html')

@app.route('/ask', methods=['POST'])
def ask():
    question = request.json.get('question')
    logging.info(f"Received question: {question}")
    try:
        response = promptinstance | groqllm | StrOutputParser()
        answer = response.invoke({'question': question})

        formatted_answer = format_answer(answer)
        logging.info(f"Response generated: {formatted_answer}")
        return jsonify({'answer': formatted_answer})
    except Exception as e:
        logging.error(f"Error generating response: {str(e)}")
        return jsonify({'answer': f'Error processing your request: {str(e)}'}), 500

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
    img = load_img(image_path, target_size=(225, 225))
    x = img_to_array(img)
    x = x.astype('float32') / 255.
    x = np.expand_dims(x, axis=0)
    predictions = model.predict(x)[0]
    return predictions

@app.route('/weather')
def weather():
    lat, lon = 12, 77  # Set the coordinates for the map
    weather_data = fetch_weather(lat, lon)

    if weather_data:
        main = weather_data.get('main', {})
        wind = weather_data.get('wind', {})
        weather_details = weather_data.get('weather', [{}])[0]
        sys = weather_data.get('sys', {})

        weather_info = {
            'name': weather_data.get('name', 'Unknown'),
            'country': sys.get('country', 'Unknown'),
            'temperature': main.get('temp', 'Not available'),
            'feels_like': main.get('feels_like', 'Not available'),
            'description': weather_details.get('description', 'Not available'),
            'humidity': main.get('humidity', 'Not available'),
            'pressure': main.get('pressure', 'Not available'),
            'wind_speed': wind.get('speed', 'Not available'),
            'wind_gust': wind.get('gust', 'Not available'),
            'visibility': weather_data.get('visibility', 'Not available'),
            'lat': lat,
            'lon': lon
        }
    else:
        weather_info = {
            'name': 'Not available',
            'country': 'Not available',
            'temperature': 'Not available',
            'feels_like': 'Not available',
            'description': 'Not available',
            'humidity': 'Not available',
            'pressure': 'Not available',
            'wind_speed': 'Not available',
            'wind_gust': 'Not available',
            'visibility': 'Not available',
            'lat': lat,
            'lon': lon
        }

    return render_template('weather.html', weather_data=weather_info)

def fetch_weather(lat, lon):
    # OpenWeatherMap API URL with your API key
    WEATHER_API_KEY = "e10f65c590d431935edaaf55555c6146"
    WEATHER_API_URL = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={WEATHER_API_KEY}&units=metric"
    
    try:
        response = requests.get(WEATHER_API_URL)
        response.raise_for_status()  # Raise an error for bad status codes
        weather_data = response.json()  # Parse the JSON response
        logging.info(f"Weather data fetched: {weather_data}")

        # Return the weather data
        return weather_data

    except Exception as e:
        logging.error(f"Error fetching weather data: {str(e)}")
        return None
    
if __name__ == "__main__":
    app.run(debug=True)
