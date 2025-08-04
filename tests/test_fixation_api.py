import unittest
import tempfile
import shutil
from datetime import date
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app as fastapi_app
from app.database import Base, get_db
from app.models.client import Client

# Ensure all models are imported and registered with Base
import app.models.client


def make_client(**overrides):
    """Factory function to create test clients with all required fields"""
    from datetime import date, datetime, timezone
    from tests.utils import gen_valid_id
    import random
    
    # Generate unique valid Israeli ID for this client
    unique_id = gen_valid_id()
    unique_email = f"test_{random.randint(1000, 9999)}@example.com"
    
    base = dict(
        id_number_raw=unique_id,
        id_number=unique_id,  # אל תסמוך על טריגר שיחשב את זה
        full_name="ישראל ישראלי",
        first_name="ישראל",
        last_name="ישראלי",
        birth_date=date(1980, 1, 1),
        current_employer_exists=False,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        phone="050-1234567",
        email=unique_email,
    )
    base.update(overrides)
    return Client(**base)


# Create test database for testing
from sqlalchemy.pool import StaticPool
TEST_DB_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DB_URL, 
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def setup_module(_module):
    """Set up test database before running tests"""
    # Import all models to ensure they're registered with Base
    from app.models.client import Client
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    # Override dependency here where fastapi_app is definitely available
    fastapi_app.dependency_overrides[get_db] = override_get_db


def teardown_module(_module):
    """Clean up test database after running tests"""
    Base.metadata.drop_all(bind=engine)
    # Clear dependency overrides
    fastapi_app.dependency_overrides.clear()
    import os
    if os.path.exists("test_fixation.db"):
        os.remove("test_fixation.db")


class TestFixationAPI(unittest.TestCase):
    """Integration tests for rights fixation API endpoints"""

    def setUp(self):
        """Set up test database and client before each test"""
        # Import all models to ensure they're registered with Base
        from app.models.client import Client
        
        # Create tables if they don't exist
        Base.metadata.create_all(bind=engine)
        
        # Override dependency for this test
        fastapi_app.dependency_overrides[get_db] = override_get_db
        
        self.client = TestClient(fastapi_app)
        
        # Create a test client in the database
        db = TestingSessionLocal()
        try:
            test_client = make_client(
                gender="male",
                marital_status="single",
                self_employed=False,
                current_employer_exists=True
            )
            db.add(test_client)
            db.commit()
            db.refresh(test_client)
            self.test_client_id = test_client.id
        finally:
            db.close()

    def tearDown(self):
        """Clean up after each test"""
        # Drop all tables
        Base.metadata.drop_all(bind=engine)

    def test_fixation_endpoints_exist(self):
        """Test that all fixation endpoints are accessible"""
        # Test 161d endpoint
        response = self.client.post(f"/api/v1/fixation/{self.test_client_id}/161d")
        # Should not return 404 (endpoint exists)
        self.assertNotEqual(response.status_code, 404)
        
        # Test grants appendix endpoint
        response = self.client.post(f"/api/v1/fixation/{self.test_client_id}/grants-appendix")
        self.assertNotEqual(response.status_code, 404)
        
        # Test commutations appendix endpoint
        response = self.client.post(f"/api/v1/fixation/{self.test_client_id}/commutations-appendix")
        self.assertNotEqual(response.status_code, 404)
        
        # Test complete package endpoint
        response = self.client.post(f"/api/v1/fixation/{self.test_client_id}/package")
        self.assertNotEqual(response.status_code, 404)

    def test_client_not_found(self):
        """Test behavior when client doesn't exist"""
        non_existent_id = 99999
        
        response = self.client.post(f"/api/v1/fixation/{non_existent_id}/161d")
        self.assertEqual(response.status_code, 404)
        
        data = response.json()
        self.assertIn("error", data["detail"])
        self.assertIn("לקוח לא נמצא", data["detail"]["error"])

    def test_inactive_client(self):
        """Test behavior when client is inactive"""
        # Create inactive client
        db = TestingSessionLocal()
        try:
            # Use make_client to generate unique ID and email
            inactive_client = make_client(
                full_name="לקוח לא פעיל",
                first_name="לקוח",
                last_name="לא פעיל",
                birth_date=date(1985, 5, 15),
                is_active=False  # Inactive client
            )
            db.add(inactive_client)
            db.commit()
            db.refresh(inactive_client)
            inactive_id = inactive_client.id
        finally:
            db.close()
        
        response = self.client.post(f"/api/v1/fixation/{inactive_id}/161d")
        self.assertEqual(response.status_code, 400)
        
        data = response.json()
        self.assertIn("error", data["detail"])
        self.assertIn("לא פעיל", data["detail"]["error"])

    def test_api_response_structure(self):
        """Test that API responses have the expected structure"""
        # Note: This test may fail if the rights fixation system is not properly set up
        # but it will test the API structure
        
        response = self.client.post(f"/api/v1/fixation/{self.test_client_id}/161d")
        
        # Response should be JSON
        self.assertEqual(response.headers.get("content-type"), "application/json")
        
        data = response.json()
        
        # Check if it's a success response or error response
        if response.status_code == 200:
            # Success response structure
            self.assertIn("success", data)
            self.assertIn("message", data)
            self.assertIn("file_path", data)
            self.assertIn("client_id", data)
            self.assertIn("client_name", data)
        else:
            # Error response structure
            self.assertIn("detail", data)

    def test_package_endpoint_response_structure(self):
        """Test that package endpoint returns proper structure"""
        response = self.client.post(f"/api/v1/fixation/{self.test_client_id}/package")
        
        self.assertEqual(response.headers.get("content-type"), "application/json")
        data = response.json()
        
        if response.status_code == 200:
            # Success response should have files structure
            self.assertIn("success", data)
            self.assertIn("message", data)
            self.assertIn("client_id", data)
            self.assertIn("client_name", data)
            self.assertIn("files", data)
            
            # Files should be a list of file paths
            files = data["files"]
            self.assertIsInstance(files, list)
            self.assertEqual(len(files), 3)  # Should have 3 files: 161d, grants, commutations
        else:
            self.assertIn("detail", data)

    def test_grants_appendix_endpoint_response_structure(self):
        """Test that grants appendix endpoint returns proper structure"""
        response = self.client.post(f"/api/v1/fixation/{self.test_client_id}/grants-appendix")
        
        self.assertEqual(response.headers.get("content-type"), "application/json")
        data = response.json()
        
        if response.status_code == 200:
            # Success response structure
            self.assertIn("success", data)
            self.assertIn("message", data)
            self.assertIn("file_path", data)
            self.assertIn("client_id", data)
            self.assertIn("client_name", data)
            self.assertTrue(data["success"])
            self.assertEqual(data["client_id"], self.test_client_id)
        else:
            self.assertIn("detail", data)

    def test_commutations_appendix_endpoint_response_structure(self):
        """Test that commutations appendix endpoint returns proper structure"""
        response = self.client.post(f"/api/v1/fixation/{self.test_client_id}/commutations-appendix")
        
        self.assertEqual(response.headers.get("content-type"), "application/json")
        data = response.json()
        
        if response.status_code == 200:
            # Success response structure
            self.assertIn("success", data)
            self.assertIn("message", data)
            self.assertIn("file_path", data)
            self.assertIn("client_id", data)
            self.assertIn("client_name", data)
            self.assertTrue(data["success"])
            self.assertEqual(data["client_id"], self.test_client_id)
        else:
            self.assertIn("detail", data)

    def test_hebrew_error_messages(self):
        """Test that error messages are in Hebrew"""
        # Test with non-existent client
        response = self.client.post("/api/v1/fixation/99999/161d")
        data = response.json()
        
        error_message = data["detail"]["error"]
        # Check that the error message contains Hebrew characters
        self.assertTrue(any('\u0590' <= char <= '\u05FF' for char in error_message))


if __name__ == "__main__":
    unittest.main()
