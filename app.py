import os
import numpy as np
# from tensorflow import lite
# from tensorflow.keras.preprocessing.image import load_img, img_to_array
from flask import Flask, render_template, request, jsonify, flash, send_from_directory, session
from flask_babel import Babel, _
from werkzeug.utils import secure_filename
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
import logging
from urllib.parse import urlparse
import html
import pandas as pd
from bs4 import BeautifulSoup
from collections import OrderedDict
import gdown  # To download the model from Google Drive
from langdetect import detect, DetectorFactory
from langdetect.lang_detect_exception import LangDetectException
from gtts import gTTS
import time
import json

# Ensure consistent language detection
DetectorFactory.seed = 0

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "your_secret_key")

# Configure logging
logging.basicConfig(level=logging.INFO)

# Google Drive link for the model
# drive_link = "https://drive.google.com/file/d/1rFdr51QVWy3mpzWPCYgdRH1XCH7Yefv6"  # Model ID extracted
# model_path = os.getenv("MODEL_PATH", "my_model.tflite")

# # Function to download model from Google Drive
# def download_model_from_drive(drive_link, destination):
#     if not os.path.exists(destination):
#         try:
#             logging.info('Downloading model from Google Drive...')
#             gdown.download(drive_link, destination, quiet=False)
#             logging.info('Model downloaded successfully.')
#         except Exception as e:
#             logging.error(f"Error downloading model: {str(e)}")
#             raise e

# labels = {0: 'Healthy', 1: 'Powdery', 2: 'Rust'}

# # Download and load the TensorFlow Lite model
# download_model_from_drive(drive_link, model_path)

# # Load the TensorFlow Lite model using the interpreter
# interpreter = lite.Interpreter(model_path=model_path)
# interpreter.allocate_tensors()

# logging.info('Model loaded. Check http://127.0.0.1:5000/')

# Load the language model
groqllm = ChatGroq(model="llama3-8b-8192", temperature=0)
prompt = """(System: You are a crop assistant designed to give responses in the primary language as English. However, if the user asks a question in any language you should respond in the same language as the input. If the language is not one of these, the response will be in English. The system should detect the language of the input and provide a response accordingly. Do not repeat points and keep the response clear and concise.)

(user: Question: {question})"""
promptinstance = ChatPromptTemplate.from_template(prompt)

# Create a directory for storing the audio files if it doesn't exist
AUDIO_DIR = os.path.join(os.getcwd(), 'static', 'audio')
os.makedirs(AUDIO_DIR, exist_ok=True)

# Path to the Excel files
EXCEL_FILE_INSECTICIDES = "all_crops_insecticides_sheets.xlsx"
EXCEL_FILE_FUNGICIDES = "all_crops_fungicides_sheets.xlsx"
EXCEL_FILE_HERBICIDES = "all_herb_sheets.xlsx"
EXCEL_PGR = "all_pgr_sheets.xlsx"

# Define the expected column order
COLUMNS = [
    "Crop",
    "Pest(Disease)",
    "Pesticide",
    "a.i (gm)",
    "Formulation (gm/ml)",
    "Dilution in Water (Liter)",
    "Waiting Period (in days)"
]
HERBICIDE_COLUMNS = [
    "Herbicide name & approved Crops",
    "Weed species",
    "Herbicide",
    "a.i (gm/Kg)",
    "Formulati on in (gm/ ml /Kg/ ltr)",
    "Dilution in Water (Liter)",
    "Waiting period/PHI between last application & harvest (days)"
]
# Define the expected column order
PGR_COLUMNS = [
    "Name of PGR & approved Crops",
    "Time of application / purpose",
    "Registered PLANT GROWTH REGULATORS (PGR)",
    "a.i (gm/Kg)",
    "Formulati on in (gm/ ml /Kg/ ltr)",
    "Dilution in Water (Liter)",
    "Waiting period/PHI between last application & harvest (days)"
]

@app.route('/')
def index():
    return render_template('index.html')

# Insecticides route
@app.route('/insecticides')
def insecticides():
    try:
        excel_data = pd.ExcelFile(EXCEL_FILE_INSECTICIDES)
        crops = excel_data.sheet_names
    except Exception as e:
        crops = []
        logging.error(f"Error loading insecticides Excel file: {e}")
    return render_template('insecticides.html', crops=crops)

# Fungicides route
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
        excel_data = pd.ExcelFile(EXCEL_FILE_HERBICIDES)  # Ensure this file exists
        crops = excel_data.sheet_names
    except Exception as e:
        crops = []
        logging.error(f"Error loading herbicides Excel file: {e}")
    return render_template('herbicides.html', crops=crops)

@app.route('/pgr')
def pgr():
    try:
        excel_data = pd.ExcelFile(EXCEL_FILE_HERBICIDES)  # Ensure this file exists
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

# @app.route('/predict', methods=['POST'])
# def upload():
#     if 'file' not in request.files:
#         return jsonify({'prediction': 'No image uploaded'}), 400

#     f = request.files['file']
#     uploads_dir = os.path.join(os.path.dirname(__file__), 'uploads')
#     os.makedirs(uploads_dir, exist_ok=True)

#     file_path = os.path.join(uploads_dir, secure_filename(f.filename))
#     f.save(file_path)
#     try:
#         predictions = getResult(file_path)
#         predicted_label = labels[np.argmax(predictions)]
#         return jsonify({'prediction': predicted_label})
#     except Exception as e:
#         logging.error(f"Error processing image: {str(e)}")
#         return jsonify({'prediction': f'Error processing image: {str(e)}'}), 500

# def getResult(image_path):
#     """
#     Process the uploaded image and predict the crop disease using TensorFlow Lite model.
#     """
#     # Load the image
#     img = load_img(image_path, target_size=(225, 225))
#     x = img_to_array(img)
#     x = x.astype('float32') / 255.
#     x = np.expand_dims(x, axis=0)

#     # Set the input tensor
#     input_details = interpreter.get_input_details()
#     interpreter.set_tensor(input_details[0]['index'], x)

#     # Run inference
#     interpreter.invoke()

#     # Get the output tensor
#     output_details = interpreter.get_output_details()
#     predictions = interpreter.get_tensor(output_details[0]['index'])[0]
    return predictions

@app.route('/get_insecticides_data', methods=['POST'])
def get_insecticides_data():
    crop_name = request.form['crop_name']
    try:
        # Load insecticides Excel file
        excel_data = pd.ExcelFile(EXCEL_FILE_INSECTICIDES)
        
        if crop_name in excel_data.sheet_names:
            # Parse the sheet without assuming any header row
            crop_data = excel_data.parse(crop_name, header=None)
            
            # Ensure the dataframe has at least as many columns as headers
            crop_data = crop_data.iloc[:, :len(COLUMNS)]
            
            # Assign the expected headers explicitly
            crop_data.columns = COLUMNS
            
            # Reorder the columns to match the expected order
            crop_data = crop_data[COLUMNS]
            
            # Fill missing values with empty strings
            crop_data = crop_data.fillna("")

            # Add Sl. No. column
            crop_data.insert(0, "Sl. No.", range(1, len(crop_data) + 1))

            # Convert to list of OrderedDicts to preserve column order
            crop_data_json = []
            for _, row in crop_data.iterrows():
                ordered_row = OrderedDict()
                for col in crop_data.columns:
                    ordered_row[col] = row[col]
                crop_data_json.append(ordered_row)
                
            return jsonify({
                "columns": crop_data.columns.tolist(),
                "data": crop_data_json
            })
        else:
            return jsonify({"error": "Crop sheet not found."})
    except Exception as e:
        return jsonify({"error": f"Error reading data: {e}"})

@app.route('/get_fungicides_data', methods=['POST'])
def get_fungicides_data():
    crop_name = request.form['crop_name']
    try:
        # Load fungicides Excel file
        excel_data = pd.ExcelFile(EXCEL_FILE_FUNGICIDES)
        
        if crop_name in excel_data.sheet_names:
            # Parse the sheet without assuming any header row
            crop_data = excel_data.parse(crop_name, header=None)
            
            # Ensure the dataframe has at least as many columns as headers
            crop_data = crop_data.iloc[:, :len(COLUMNS)]
            
            # Assign the expected headers explicitly
            crop_data.columns = COLUMNS
            
            # Reorder the columns to match the expected order
            crop_data = crop_data[COLUMNS]
            
            # Fill missing values with empty strings
            crop_data = crop_data.fillna("")

            # Add Sl. No. column
            crop_data.insert(0, "Sl. No.", range(1, len(crop_data) + 1))

            # Convert to list of OrderedDicts to preserve column order
            crop_data_json = []
            for _, row in crop_data.iterrows():
                ordered_row = OrderedDict()
                for col in crop_data.columns:
                    ordered_row[col] = row[col]
                crop_data_json.append(ordered_row)
                
            return jsonify({
                "columns": crop_data.columns.tolist(),
                "data": crop_data_json
            })
        else:
            return jsonify({"error": "Crop sheet not found."})
    except Exception as e:
        return jsonify({"error": f"Error reading data: {e}"})

@app.route('/get_herbicides_data', methods=['POST'])
def get_herbicides_data():
    crop_name = request.form['crop_name']
    try:
        # Load herbicides Excel file
        excel_data = pd.ExcelFile(EXCEL_FILE_HERBICIDES)
        
        if crop_name in excel_data.sheet_names:
            # Parse the sheet without assuming any header row
            crop_data = excel_data.parse(crop_name, header=None)
            
            # Ensure the dataframe has at least as many columns as headers
            crop_data = crop_data.iloc[:, :len(HERBICIDE_COLUMNS)]
            
            # Assign the expected headers explicitly
            crop_data.columns = HERBICIDE_COLUMNS
            
            # Reorder the columns to match the expected order
            crop_data = crop_data[HERBICIDE_COLUMNS]
            
            # Fill missing values with empty strings
            crop_data = crop_data.fillna("")

            # Add Sl. No. column
            crop_data.insert(0, "Sl. No.", range(1, len(crop_data) + 1))

            # Convert to list of OrderedDicts to preserve column order
            crop_data_json = []
            for _, row in crop_data.iterrows():
                ordered_row = OrderedDict()
                for col in crop_data.columns:
                    ordered_row[col] = row[col]
                crop_data_json.append(ordered_row)
                
            return jsonify({
                "columns": crop_data.columns.tolist(),
                "data": crop_data_json
            })
        else:
            return jsonify({"error": "Crop sheet not found."})
    except Exception as e:
        logging.error(f"Error reading herbicide data: {e}")
        return jsonify({"error": f"Error reading data: {e}"})
    
@app.route('/get_pgr_data', methods=['POST'])
def get_pgr_data():
    crop_name = request.form['crop_name']
    try:
        # Load herbicides Excel file
        excel_data = pd.ExcelFile(EXCEL_PGR)
        
        if crop_name in excel_data.sheet_names:
            # Parse the sheet without assuming any header row
            crop_data = excel_data.parse(crop_name, header=None)
            
            # Ensure the dataframe has at least as many columns as headers
            crop_data = crop_data.iloc[:, :len(HERBICIDE_COLUMNS)]
            
            # Assign the expected headers explicitly
            crop_data.columns = HERBICIDE_COLUMNS
            
            # Reorder the columns to match the expected order
            crop_data = crop_data[HERBICIDE_COLUMNS]
            
            # Fill missing values with empty strings
            crop_data = crop_data.fillna("")

            # Add Sl. No. column
            crop_data.insert(0, "Sl. No.", range(1, len(crop_data) + 1))

            # Convert to list of OrderedDicts to preserve column order
            crop_data_json = []
            for _, row in crop_data.iterrows():
                ordered_row = OrderedDict()
                for col in crop_data.columns:
                    ordered_row[col] = row[col]
                crop_data_json.append(ordered_row)
                
            return jsonify({
                "columns": crop_data.columns.tolist(),
                "data": crop_data_json
            })
        else:
            return jsonify({"error": "Crop sheet not found."})
    except Exception as e:
        logging.error(f"Error reading herbicide data: {e}")
        return jsonify({"error": f"Error reading data: {e}"})
    
#Soil Implementation
excel_file = "Soil_Labs_By_State1.xlsx"
df_all_sheets = pd.read_excel(excel_file, sheet_name=None)  # Read all sheets into a dictionary of DataFrames

@app.route('/soil_labs')
def soil_labs():
    """Render HTML template with all unique states."""
    # Combine all dataframes into one
    df_combined = pd.concat(df_all_sheets.values(), ignore_index=True)
    
    # Get unique states from all sheets
    states = df_combined['State'].dropna().unique().tolist()
    return render_template("soil_labs.html", states=states)

@app.route("/get_districts", methods=["GET"])
def get_districts():
    """Fetch unique districts based on the selected state from all sheets."""
    state = request.args.get("state")
    if state:
        # Combine all dataframes into one and filter by state
        df_combined = pd.concat(df_all_sheets.values(), ignore_index=True)

        # Clean state names to avoid issues with special characters or spaces
        df_combined['State'] = df_combined['State'].str.replace('&', 'and').str.strip()

        # Clean the input state as well
        state_clean = state.replace('&', 'and').strip()

        # Get unique districts for the selected state
        districts = df_combined[df_combined['State'] == state_clean]['District'].dropna().unique().tolist()

        return jsonify(districts)
    
    return jsonify([]) 


@app.route("/get_data", methods=["GET"])
def get_data():
    state = request.args.get("state")
    district = request.args.get("district")

    if state and district:
        # Combine all dataframes into one and filter by state and district
        df_combined = pd.concat(df_all_sheets.values(), ignore_index=True)
        data_filtered = df_combined[(df_combined['State'] == state) & (df_combined['District'] == district)]

        if data_filtered.empty:
            return jsonify([])

        return jsonify(data_filtered.to_dict(orient="records"))

    return jsonify([])

#Karnataka Market Data
URLS = {
    "Egg Prices": "https://daatacenter.com/trade/today-egg-rate-bangalore/",
    "Chicken Rates": "https://daatacenter.com/chicken-rate/chicken-rate-today-in-bangalore/",
    "Vegetable Prices": "https://market.todaypricerates.com/Bengaluru-vegetables-price-in-Karnataka",
    "Petrol Prices": "https://www.ndtv.com/fuel-prices/petrol-price-in-bangalore-city",
    "Diesel Prices": "https://www.ndtv.com/fuel-prices/diesel-price-in-bangalore-city",
    "Fruit Prices": "https://market.todaypricerates.com/Karnataka-fruits-price",
    "Flower Rates": "https://daatacenter.com/flowers-price/today-flower-rate-in-bangalore-market/",
}

def scrape_table(url):
    """Scrape table or div data from the specified URL."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # Special case for petrol and diesel prices with div id="myID"
        if "ndtv.com" in url:
            div = soup.find("div", id="myID")
            if div:
                rows = div.find_all("tr")
                if rows:
                    headers_row = rows[0]
                    table_headers = [cell.text.strip() for cell in headers_row.find_all(["th", "td"])]

                    # Remove "Change" column if it exists
                    if "Change" in table_headers:
                        change_index = table_headers.index("Change")
                        table_headers.pop(change_index)
                    else:
                        change_index = None

                    # Extract rows without "Change" column
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

        # Generic table scraping logic
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
    """Render the index page and handle form submissions."""
    selected_category = None
    table_headers = []
    table_rows = []
    error_message = None

    if request.method == "POST":
        selected_category = request.form.get("category")
        if selected_category in URLS:
            url = URLS[selected_category]
            result = scrape_table(url)

            if isinstance(result[0], str):  # Error occurred
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

#News_Module
nltk.data.path.append(os.path.join(os.path.dirname(__file__), "nltk_data"))

# Now download will work without errors
nltk.download('vader_lexicon', download_dir=nltk.data.path[0])

app.secret_key = 'your_secret_key_here'
logging.basicConfig(level=logging.DEBUG)

# Updated RSS Feed URLs including The Hindu sources
RSS_FEEDS = {
    "india": "https://feeds.feedburner.com/ndtvnews-india-news",
    "world": "https://feeds.feedburner.com/ndtvnews-world-news",
    "education": {
        "The Hindu Education": "https://www.thehindu.com/education/feeder/default.rss",
    },
    "agriculture": {
        "The Hindu Agriculture": "https://www.thehindu.com/sci-tech/agriculture/feeder/default.rss"
    },
    "health": "https://www.thehindu.com/sci-tech/health/feeder/default.rss",
    "sports": "https://www.thehindu.com/sport/feeder/default.rss",
    "economy": "https://www.thehindu.com/business/Economy/feeder/default.rss"
}

sia = SentimentIntensityAnalyzer()

def clean_html_content(text):
    """Remove HTML tags and decode HTML entities."""
    text = html.unescape(text)  # Decode HTML entities
    for tag in ['<p>', '</p>', '<br>', '<br/>', '<br />', '<div>', '</div>']:
        text = text.replace(tag, ' ')
    return text.strip()

def analyze_sentiment(text):
    """Perform sentiment analysis and return the sentiment label."""
    score = sia.polarity_scores(text)['compound']
    if score >= 0.05:
        return "Positive 😊"
    elif score <= -0.05:
        return "Negative 😞"
    else:
        return "Neutral 😐"

def validate_feed_url(url):
    """Validate the feed URL structure."""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False

def fetch_feed(url, source_name=""):
    """Fetch and parse the RSS feed with error handling."""
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
    """Process a single feed entry and return article data."""
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

from dateutil import parser

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

    # **Sort articles by most recent first**
    def get_published_date(article):
        try:
            return parser.parse(article['published'])
        except (ValueError, TypeError):
            return None

    articles = sorted([a for a in articles if get_published_date(a) is not None], 
                      key=get_published_date, reverse=True)

    return render_template('news.html', articles=articles, category=category)

#Mandi Data
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

import os

if __name__ == '__main__':
    port = int(os.getenv("PORT", 10000))  # Use Render's assigned port or default to 10000
    app.run(host="0.0.0.0", port=port, debug=True)
