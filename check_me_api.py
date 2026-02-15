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
url = "http://localhost:8000/auth/users/me"
req = urllib.request.Request(url, headers=headers)

try:
    with urllib.request.urlopen(req) as response:
        me = json.loads(response.read().decode())
        print("Me:")
        print(me)
except Exception as e:
    print(f"Get me failed: {e}")
