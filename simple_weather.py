#!/usr/bin/env python3
import urllib.request
import json

# City coordinates
cities = {
    "广州": (23.1291, 113.2644),
    "深圳": (22.5431, 114.0579),
    "上海": (31.2304, 121.4737)
}

print("=== 中国主要城市天气查询 ===")
print()

for city, (lat, lon) in cities.items():
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
        
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode())
            current = data['current_weather']
            
            temp = current['temperature']
            wind = current['windspeed']
            code = current['weathercode']
            
            # Weather code mapping
            weather_map = {
                0: "晴天",
                1: "基本晴朗", 
                2: "局部多云",
                3: "阴天",
                45: "雾",
                48: "雾凇",
                51: "小雨",
                53: "中雨",
                55: "大雨",
                61: "小雨",
                63: "中雨",
                65: "大雨",
                80: "小雨",
                81: "中雨", 
                82: "暴雨"
            }
            
            weather_desc = weather_map.get(code, f"天气代码: {code}")
            
            print(f"{city}:")
            print(f"  温度: {temp}°C")
            print(f"  风速: {wind} km/h")
            print(f"  天气: {weather_desc}")
            print()
            
    except Exception as e:
        print(f"{city}: 查询失败 - {str(e)}")
        print()

print("=== 查询完成 ===")