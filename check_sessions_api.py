import urllib.request
import json

# Login
url = "http://localhost:8000/auth/token"
data = {"username": "admin", "password": "admin123"}
data_encoded = urllib.parse.urlencode(data).encode()
req = urllib.request.Request(url, data=data_encoded, method='POST')

try:
    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read().decode())
        token = result["access_token"]
        print("Login Success")
except Exception as e:
    print(f"Login failed: {e}")
    exit()

headers = {"Authorization": f"Bearer {token}"}
url = "http://localhost:8000/sessions"
req = urllib.request.Request(url, headers=headers)

try:
    with urllib.request.urlopen(req) as response:
        sessions = json.loads(response.read().decode())
        print("Sessions:")
        print(sessions)
except Exception as e:
    print(f"Get sessions failed: {e}")
