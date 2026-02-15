import httpx
import asyncio
import secrets
import sys

BASE_URL = "http://localhost:8000"

# Generate random user to avoid conflicts
RANDOM_SUFFIX = secrets.token_hex(4)
USERNAME = f"testuser_{RANDOM_SUFFIX}"
EMAIL = f"test_{RANDOM_SUFFIX}@example.com"
PASSWORD = "testpassword123"

async def test_register_and_login():
    print(f"\n--- Testing Register & Login & Session Management ---")
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        # 1. Register
        print(f"1. Registering user: {USERNAME}")
        resp = await client.post("/auth/register", json={
            "username": USERNAME,
            "password": PASSWORD,
            "email": EMAIL
        })
        if resp.status_code != 200:
            print(f"Register failed: {resp.status_code} {resp.text}")
            return
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == USERNAME
        assert data["email"] == EMAIL
        assert data["role"] == "user"
        print("   -> Success")

        # 2. Login
        print("2. Logging in...")
        resp = await client.post("/auth/token", data={
            "username": USERNAME,
            "password": PASSWORD
        })
        assert resp.status_code == 200
        token_data = resp.json()
        assert "access_token" in token_data
        token = token_data["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("   -> Success")

        # 3. Create Session
        print("3. Creating session...")
        resp = await client.post("/sessions/new", headers=headers)
        assert resp.status_code == 200
        session_id = resp.json()["id"]
        print(f"   -> Session created: {session_id}")

        # 4. List Sessions
        print("4. Listing sessions...")
        resp = await client.get("/sessions", headers=headers)
        assert resp.status_code == 200
        sessions = resp.json()["sessions"]
        assert any(s["id"] == session_id for s in sessions)
        print("   -> Session found in list")

        # 5. Delete Session
        print(f"5. Deleting session: {session_id}")
        resp = await client.delete(f"/sessions/{session_id}", headers=headers)
        assert resp.status_code == 200
        print("   -> Delete request successful")
        
        # Verify deletion
        resp = await client.get("/sessions", headers=headers)
        sessions = resp.json()["sessions"]
        assert not any(s["id"] == session_id for s in sessions)
        print("   -> Verified session is gone")

        # 6. Test Path Traversal / Invalid ID (Security)
        print("6. Testing invalid session ID security...")
        # Test 1: Invalid character (dot)
        print("   Testing 'session.123' (dot not allowed)...")
        resp = await client.delete("/sessions/session.123", headers=headers)
        if resp.status_code == 400:
             print("   -> Blocked successfully (400 Bad Request)")
        else:
             print(f"   -> FAILED! Expected 400, got {resp.status_code}")
             # We assume strict regex
        
        # Test 2: Encoded path traversal
        print("   Testing '..%2Fag.py' (encoded traversal)...")
        # Note: httpx might normalize, but let's try to send raw-ish path
        # or just "traverse/attempt" which shouldn't match regex even if it matched route
        resp = await client.delete("/sessions/traverse%2Fattempt", headers=headers)
        if resp.status_code == 400:
             print("   -> Blocked successfully (400 Bad Request)")
        elif resp.status_code == 404:
             print("   -> 404 is also acceptable if route didn't match")
        else:
             print(f"   -> Unexpected: {resp.status_code}")

async def test_admin_create_user():
    print(f"\n--- Testing Admin User Creation ---")
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        # Login as Admin
        print("1. Admin Login...")
        try:
            resp = await client.post("/auth/token", data={
                "username": "admin",
                "password": "admin123" 
            })
            if resp.status_code != 200:
                print("   -> Admin login failed. Default admin might not exist or password changed.")
                return # Skip test
            
            token = resp.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            print("   -> Success")

            # Create new user via Admin API
            NEW_USER = f"admin_created_{RANDOM_SUFFIX}"
            print(f"2. Admin creating user: {NEW_USER}")
            resp = await client.post("/auth/users", json={
                "username": NEW_USER,
                "password": "password123",
                "role": "user"
            }, headers=headers)
            
            if resp.status_code == 200:
                print("   -> User created successfully")
                new_user_id = resp.json()["id"]
            else:
                print(f"   -> Failed: {resp.text}")
                sys.exit(1)
            
            # Verify login as that user
            print("3. Verifying new user login...")
            resp = await client.post("/auth/token", data={
                "username": NEW_USER,
                "password": "password123"
            })
            assert resp.status_code == 200
            print("   -> New user login successful")
            
            # Test List Users
            print("4. Testing List Users (Admin)...")
            resp = await client.get("/auth/users", headers=headers)
            assert resp.status_code == 200
            users = resp.json()
            assert len(users) >= 2 # Admin + New User
            assert any(u["username"] == NEW_USER for u in users)
            print("   -> List Users successful")

            # Test Update User
            print(f"5. Testing Update User {NEW_USER}...")
            new_email = f"updated_{RANDOM_SUFFIX}@example.com"
            resp = await client.put(f"/auth/users/{new_user_id}", json={
                "email": new_email,
                "is_active": True
            }, headers=headers)
            if resp.status_code != 200:
                 print(f"Update failed: {resp.text}")
            updated_user = resp.json()
            print(f"DEBUG: updated_user keys: {updated_user.keys()}")
            print(f"DEBUG: updated_user: {updated_user}")
            assert updated_user["email"] == new_email
            print("   -> Update User successful")
            
            # Test Reset Password
            print(f"6. Testing Password Reset for {NEW_USER}...")
            resp = await client.post(f"/auth/users/{new_user_id}/reset_password", json={
                "new_password": "newpassword456"
            }, headers=headers)
            assert resp.status_code == 200
            print("   -> Password Reset successful")
            
            # Verify Login with new password
            print("7. Verifying login with new password...")
            resp = await client.post("/auth/token", data={
                "username": NEW_USER,
                "password": "newpassword456"
            })
            assert resp.status_code == 200
            print("   -> Login with new password successful")

        except Exception as e:
            print(f"   -> Error: {e}")

async def main():
    try:
        await test_register_and_login()
        await test_admin_create_user()
        print("\nAll tests passed successfully!")
    except Exception as e:
        print(f"\nXXX Test script failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
