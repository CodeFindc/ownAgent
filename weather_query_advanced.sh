#!/bin/bash

echo "=== 天气查询清单 ==="
echo "1. 广州 (Guangzhou)"
echo "2. 深圳 (Shenzhen)" 
echo "3. 上海 (Shanghai)"
echo ""

echo "正在查询天气..."
echo ""

# Function to get weather description from weather code
function get_weather_desc() {
    case $1 in
        0) echo "晴天" ;;
        1) echo "大部分晴天" ;;
        2) echo "部分多云" ;;
        3) echo "多云" ;;
        45) echo "雾" ;;
        48) echo "冻雾" ;;
        51) echo "小雨" ;;
        53) echo "中雨" ;;
        55) echo "大雨" ;;
        56) echo "冻小雨" ;;
        57) echo "冻大雨" ;;
        61) echo "小雨" ;;
        63) echo "中雨" ;;
        65) echo "大雨" ;;
        66) echo "冻雨" ;;
        67) echo "冻大雨" ;;
        71) echo "小雪" ;;
        73) echo "中雪" ;;
        75) echo "大雪" ;;
        77) echo "雪粒" ;;
        80) echo "阵雨" ;;
        81) echo "强阵雨" ;;
        82) echo "猛烈阵雨" ;;
        85) echo "阵雪" ;;
        86) echo "强阵雪" ;;
        95) echo "雷暴" ;;
        96) echo "雷暴伴有冰雹" ;;
        99) echo "强雷暴伴有冰雹" ;;
        *) echo "未知" ;;
    esac
}

# Query Guangzhou weather (latitude: 23.13, longitude: 113.26)
echo "=== 广州天气 ==="
GUANGZHOU_JSON=$(curl -s "https://api.open-meteo.com/v1/forecast?latitude=23.13&longitude=113.26&current_weather=true")
GUANGZHOU_TEMP=$(echo $GUANGZHOU_JSON | grep -o '"temperature":[^,]*' | cut -d':' -f2)
GUANGZHOU_WIND=$(echo $GUANGZHOU_JSON | grep -o '"windspeed":[^,]*' | cut -d':' -f2)
GUANGZHOU_CODE=$(echo $GUANGZHOU_JSON | grep -o '"weathercode":[^,}]*' | cut -d':' -f2)
GUANGZHOU_DESC=$(get_weather_desc $GUANGZHOU_CODE)
echo "温度: ${GUANGZHOU_TEMP}°C"
echo "风速: ${GUANGZHOU_WIND} km/h"
echo "天气: ${GUANGZHOU_DESC}"
echo ""

# Query Shenzhen weather (latitude: 22.54, longitude: 114.05)
echo "=== 深圳天气 ==="
SHENZHEN_JSON=$(curl -s "https://api.open-meteo.com/v1/forecast?latitude=22.54&longitude=114.05&current_weather=true")
SHENZHEN_TEMP=$(echo $SHENZHEN_JSON | grep -o '"temperature":[^,]*' | cut -d':' -f2)
SHENZHEN_WIND=$(echo $SHENZHEN_JSON | grep -o '"windspeed":[^,]*' | cut -d':' -f2)
SHENZHEN_CODE=$(echo $SHENZHEN_JSON | grep -o '"weathercode":[^,}]*' | cut -d':' -f2)
SHENZHEN_DESC=$(get_weather_desc $SHENZHEN_CODE)
echo "温度: ${SHENZHEN_TEMP}°C"
echo "风速: ${SHENZHEN_WIND} km/h"
echo "天气: ${SHENZHEN_DESC}"
echo ""

# Query Shanghai weather (latitude: 31.23, longitude: 121.47)
echo "=== 上海天气 ==="
SHANGHAI_JSON=$(curl -s "https://api.open-meteo.com/v1/forecast?latitude=31.23&longitude=121.47&current_weather=true")
SHANGHAI_TEMP=$(echo $SHANGHAI_JSON | grep -o '"temperature":[^,]*' | cut -d':' -f2)
SHANGHAI_WIND=$(echo $SHANGHAI_JSON | grep -o '"windspeed":[^,]*' | cut -d':' -f2)
SHANGHAI_CODE=$(echo $SHANGHAI_JSON | grep -o '"weathercode":[^,}]*' | cut -d':' -f2)
SHANGHAI_DESC=$(get_weather_desc $SHANGHAI_CODE)
echo "温度: ${SHANGHAI_TEMP}°C"
echo "风速: ${SHANGHAI_WIND} km/h"
echo "天气: ${SHANGHAI_DESC}"
echo ""

echo "查询完成！"