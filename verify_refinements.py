import urllib.request
import urllib.parse
import json
import random

BASE_URL = "http://localhost:8000"
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"

TEST_USER_BASE = "test_reg_user"
TEST_PASS = "pass123"
NEW_PASS = "newpass123"

def make_request(url, method='GET', data=None, token=None):
    headers = {}
    if token:
        headers['Authorization'] = f"Bearer {token}"
    
    if data:
        headers['Content-Type'] = 'application/json'
        data_encoded = json.dumps(data).encode('utf-8')
    else:
        data_encoded = None

    req = urllib.request.Request(url, data=data_encoded, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req) as response:
            resp_body = response.read().decode()
            try:
                return response.status, json.loads(resp_body)
            except:
                return response.status, resp_body
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()
    except Exception as e:
        print(f"Request error: {e}")
        return 500, str(e)

def login(username, password):
    # Form data for login
    url = f"{BASE_URL}/auth/token"
    data = {"username": username, "password": password}
    data_encoded = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=data_encoded, method='POST')
    
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode())
            return result.get("access_token")
    except Exception as e:
        print(f"Login failed: {e}")
        return None

def set_registration(token, allow):
    return make_request(f"{BASE_URL}/auth/settings", 'PUT', {"key": "allow_registration", "value": str(allow).lower()}, token)

def register_user(username, password):
    return make_request(f"{BASE_URL}/auth/register", 'POST', {"username": username, "password": password})

def change_password(token, old_pass, new_pass):
    return make_request(f"{BASE_URL}/auth/users/me/password", 'PUT', {"current_password": old_pass, "new_password": new_pass}, token)

def main():
    print("Logging in as admin...")
    admin_token = login(ADMIN_USER, ADMIN_PASS)
    if not admin_token:
        print("Failed to login as admin. Ensure server is running.")
        return

    print("Disabling registration...")
    status, _ = set_registration(admin_token, False)
    if status != 200:
        print(f"Failed to set registration: {status}")
        return

    print("Attempting to register (expect failure)...")
    status, _ = register_user("should_fail_user", "pass")
    if status == 403:
        print("Success: Registration blocked as expected.")
    else:
        print(f"Failure: Registration not blocked (Status: {status})")

    print("Enabling registration...")
    status, _ = set_registration(admin_token, True)
    if status != 200:
        print(f"Failed to set registration: {status}")
        return

    print("Attempting to register (expect success)...")
    suffix = random.randint(1000, 9999)
    user = f"{TEST_USER_BASE}_{suffix}"
    
    status, _ = register_user(user, TEST_PASS)
    if status == 200:
        print(f"Success: Registered {user}.")
    else:
        print(f"Failure: Registration failed (Status: {status})")
        return

    print("Logging in as new user...")
    user_token = login(user, TEST_PASS)
    if not user_token:
        print("Failed to login as new user")
        return
    
    print("Changing password...")
    status, _ = change_password(user_token, TEST_PASS, NEW_PASS)
    if status == 200:
        print(f"Success: Password changed to {NEW_PASS}.")
    else:
        print(f"Failure: Password change failed ({status})")
        return

    print("Verifying new password login...")
    new_token = login(user, NEW_PASS)
    if new_token:
        print("Success: Login with new password works.")
    else:
        print("Failure: Login with new password failed.")

if __name__ == "__main__":
    main()
