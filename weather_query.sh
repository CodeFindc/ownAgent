#!/bin/bash

# Weather query script for Guangzhou, Shenzhen, and Shanghai

echo "=== Weather Query for Major Chinese Cities ==="
echo ""

# Query Guangzhou weather
echo "Guangzhou:"
curl -s "wttr.in/Guangzhou?format=3"
echo ""

# Query Shenzhen weather  
echo "Shenzhen:"
curl -s "wttr.in/Shenzhen?format=3"
echo ""

# Query Shanghai weather
echo "Shanghai:"
curl -s "wttr.in/Shanghai?format=3"
echo ""

echo "=== Query Complete ==="