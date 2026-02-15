
import urllib.request
import urllib.parse
import json
import time

BASE_URL = "http://127.0.0.1:8000"

def make_request(url, method="GET", data=None, headers=None):
    if headers is None:
        headers = {}
    
    if data:
        data = urllib.parse.urlencode(data).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as response:
            return response.getcode(), response.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")
    except Exception as e:
        return 0, str(e)

def run_test():
    print("=== Starting Session Reproduction Test (urllib) ===")
    
    # 1. Login
    print("\n[1] Logging in...")
    status, body = make_request(f"{BASE_URL}/auth/token", method="POST", data={
        "username": "admin",
        "password": "admin123"
    })
    
    if status != 200:
        print(f"Login failed: {body}")
        return
        
    token = json.loads(body)["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("Login successful.")

    # 2. Create Session A
    print("\n[2] Creating Session A...")
    # POST with empty body (json usually, but here params are query or none)
    # The endpoint expects nothing in body?
    # Actually fastapi expects nothing if not defined.
    # But urllib POST needs data or it becomes GET if checked?
    # Explicit method="POST" works.
    
    status, body = make_request(f"{BASE_URL}/sessions/new", method="POST", headers=headers)
    if status != 200:
        print(f"Create Session A failed: {body}")
        return
    session_a = json.loads(body)
    sid_a = session_a["id"]
    print(f"Session A Created: {sid_a}")

    # 3. Create Session B
    print("\n[3] Creating Session B...")
    status, body = make_request(f"{BASE_URL}/sessions/new", method="POST", headers=headers)
    sid_b = json.loads(body)["id"]
    print(f"Session B Created: {sid_b}")

    if sid_a == sid_b:
        print("FATAL: Session IDs are identical!")
    else:
        print("SUCCESS: Session IDs are unique.")

    # 4. List Sessions
    print("\n[4] Listing Sessions...")
    status, body = make_request(f"{BASE_URL}/sessions", method="GET", headers=headers)
    sessions = json.loads(body)["sessions"]
    print(f"Found {len(sessions)} sessions.")
    
    found_a = any(s["id"] == sid_a for s in sessions)
    found_b = any(s["id"] == sid_b for s in sessions)
    
    if found_a and found_b:
        print("SUCCESS: Both sessions found in list.")
    else:
        print(f"FAILURE: Sessions missing. A: {found_a}, B: {found_b}")

    # 5. Check Content
    print("\n[5] Checking Content...")
    # Load A
    status, body = make_request(f"{BASE_URL}/sessions/{sid_a}/load", method="POST", headers=headers)
    history_a = json.loads(body).get("history", [])
    print(f"Session A History Length: {len(history_a)}")
    
    status, body = make_request(f"{BASE_URL}/sessions/{sid_b}/load", method="POST", headers=headers)
    history_b = json.loads(body).get("history", [])
    print(f"Session B History Length: {len(history_b)}")

    if len(history_a) == 0 and len(history_b) == 0:
         print("SUCCESS: Both sessions are empty.")
    else:
         print("FAILURE: Sessions not empty.")

if __name__ == "__main__":
    run_test()
