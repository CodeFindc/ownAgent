#!/usr/bin/env python3
import requests
import json

# City coordinates (latitude, longitude)
cities = {
    "Guangzhou": (23.1291, 113.2644),
    "Shenzhen": (22.5431, 114.0579),
    "Shanghai": (31.2304, 121.4737)
}

print("=== Weather Query for Major Chinese Cities ===")
print()

for city, (lat, lon) in cities.items():
    try:
        # Query Open-Meteo API
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            current = data['current_weather']
            
            # Convert temperature from Celsius
            temp = current['temperature']
            windspeed = current['windspeed']
            weathercode = current['weathercode']
            
            # Simple weather code mapping
            weather_map = {
                0: "Clear sky",
                1: "Mainly clear", 
                2: "Partly cloudy",
                3: "Overcast",
                45: "Fog",
                48: "Depositing rime fog",
                51: "Light drizzle",
                53: "Moderate drizzle",
                55: "Dense drizzle",
                61: "Slight rain",
                63: "Moderate rain",
                65: "Heavy rain",
                80: "Slight rain showers",
                81: "Moderate rain showers", 
                82: "Violent rain showers"
            }
            
            weather_desc = weather_map.get(weathercode, f"Code {weathercode}")
            
            print(f"{city}:")
            print(f"  Temperature: {temp}°C")
            print(f"  Wind Speed: {windspeed} km/h")
            print(f"  Conditions: {weather_desc}")
            print()
            
        else:
            print(f"{city}: API request failed (Status: {response.status_code})")
            print()
            
    except Exception as e:
        print(f"{city}: Error - {str(e)}")
        print()

print("=== Query Complete ===")