import sys
import os
import unittest
# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from server import app
from auth import models, database, security
import shutil

# Setup Test Database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_settings.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[database.get_db] = override_get_db

client = TestClient(app)

class TestSettingsAndProfile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        models.Base.metadata.create_all(bind=engine)
        # Create Admin
        db = TestingSessionLocal()
        if not db.query(models.User).filter(models.User.username == "admin").first():
            admin = models.User(
                username="admin",
                hashed_password=security.get_password_hash("admin123"),
                role=models.UserRole.ADMIN
            )
            db.add(admin)
            db.commit()
        db.close()

    @classmethod
    def tearDownClass(cls):
        # Retrieve userimages to cleanup
        if os.path.exists("test_settings.db"):
            os.remove("test_settings.db")
        if os.path.exists("test_image.png"):
             os.remove("test_image.png")

    def get_admin_token(self):
        response = client.post(
            "/auth/token",
            data={"username": "admin", "password": "admin123"}
        )
        return response.json()["access_token"]

    def test_01_get_settings_public(self):
        # Public endpoint
        response = client.get("/auth/settings")
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)

    def test_02_update_settings_admin(self):
        token = self.get_admin_token()
        headers = {"Authorization": f"Bearer {token}"}
        
        # 1. Update Site Name
        response = client.put(
            "/auth/settings",
            headers=headers,
            json={"key": "site_name", "value": "Test Agent"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["value"], "Test Agent")
        
        # 2. Verify Get
        response = client.get("/auth/settings")
        settings = response.json()
        site_name = next((s for s in settings if s["key"] == "site_name"), None)
        self.assertIsNotNone(site_name)
        self.assertEqual(site_name["value"], "Test Agent")

    def test_03_avatar_upload_and_update_profile(self):
        token = self.get_admin_token()
        headers = {"Authorization": f"Bearer {token}"}
        
        # 1. Create a dummy image
        with open("test_image.png", "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")
            
        # 2. Upload
        with open("test_image.png", "rb") as f:
            response = client.post(
                "/auth/upload/avatar",
                headers=headers,
                files={"file": ("test_image.png", f, "image/png")}
            )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("url", data)
        avatar_url = data["url"]
        self.assertTrue(avatar_url.startswith("/static/userimages/"))
        
        # 3. Update User Profile with new Avatar
        # Get Admin ID first
        user_resp = client.get("/auth/users/me", headers=headers)
        user_id = user_resp.json()["id"]
        
        response = client.put(
            f"/auth/users/{user_id}",
            headers=headers,
            json={"avatar_url": avatar_url}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["avatar_url"], avatar_url)
        
        # 4. Verify in Me
        response = client.get("/auth/users/me", headers=headers)
        self.assertEqual(response.json()["avatar_url"], avatar_url)

if __name__ == "__main__":
    unittest.main()
