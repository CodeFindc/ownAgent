#!/bin/bash

# Weather query using Open-Meteo API with curl

echo "=== Weather Query for Major Chinese Cities ==="
echo ""

# Query Guangzhou weather
echo "Guangzhou:"
curl -s "https://api.open-meteo.com/v1/forecast?latitude=23.1291&longitude=113.2644&current_weather=true" | python -c "
import sys, json
data = json.load(sys.stdin)
current = data['current_weather']
print(f'  Temperature: {current[\"temperature\"]}°C')
print(f'  Wind Speed: {current[\"windspeed\"]} km/h')
print(f'  Weather Code: {current[\"weathercode\"]}')
"
echo ""

# Query Shenzhen weather
echo "Shenzhen:"
curl -s "https://api.open-meteo.com/v1/forecast?latitude=22.5431&longitude=114.0579&current_weather=true" | python -c "
import sys, json
data = json.load(sys.stdin)
current = data['current_weather']
print(f'  Temperature: {current[\"temperature\"]}°C')
print(f'  Wind Speed: {current[\"windspeed\"]} km/h')
print(f'  Weather Code: {current[\"weathercode\"]}')
"
echo ""

# Query Shanghai weather
echo "Shanghai:"
curl -s "https://api.open-meteo.com/v1/forecast?latitude=31.2304&longitude=121.4737&current_weather=true" | python -c "
import sys, json
data = json.load(sys.stdin)
current = data['current_weather']
print(f'  Temperature: {current[\"temperature\"]}°C')
print(f'  Wind Speed: {current[\"windspeed\"]} km/h')
print(f'  Weather Code: {current[\"weathercode\"]}')
"
echo ""

echo "=== Query Complete ==="