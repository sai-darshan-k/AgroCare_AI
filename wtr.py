import requests

# API Key and URL
WEATHER_API_KEY = "e10f65c590d431935edaaf55555c6146"
WEATHER_API_URL = "https://api.openweathermap.org/data/2.5/weather"

def fetch_weather(lat, lon):
    params = {
        'lat': lat,
        'lon': lon,
        'appid': WEATHER_API_KEY,
        'units': 'metric'  # Use 'metric' for Celsius or 'imperial' for Fahrenheit
    }
    
    try:
        response = requests.get(WEATHER_API_URL, params=params)
        response.raise_for_status()  # Raise an error for bad status codes
        weather_data = response.json()  # Parse the JSON response
        return weather_data
    
    except requests.exceptions.RequestException as e:
        print(f"Error fetching weather data: {e}")
        return None

def print_weather_info(weather_data):
    if weather_data:
        main = weather_data.get('main', {})
        wind = weather_data.get('wind', {})
        
        temperature = main.get('temp', 'Not available')
        humidity = main.get('humidity', 'Not available')
        pressure = main.get('pressure', 'Not available')
        wind_speed = wind.get('speed', 'Not available')
        
        print(f"Temperature: {temperature} °C")
        print(f"Humidity: {humidity} %")
        print(f"Pressure: {pressure} hPa")
        print(f"Wind Speed: {wind_speed} m/s")
    else:
        print("No weather data available.")

if __name__ == "__main__":
    # Coordinates for testing
    lat, lon = 12, 77  # You can change these coordinates to test other locations
    
    # Fetch and print weather information
    weather_data = fetch_weather(lat, lon)
    print_weather_info(weather_data)
