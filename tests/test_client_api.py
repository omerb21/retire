import unittest
from datetime import date, datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import uuid

from app.main import app
from app.database import get_db, Base
from app.models import Client, Employer, Employment, TerminationEvent


# Create in-memory SQLite database for testing
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Override the get_db dependency to use the test database
def override_get_db():
    # Use the current TestingSessionLocal (may be updated in setUp)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.rollback()  # Ensure any uncommitted changes are rolled back
        db.close()


def setup_module(_module):
    """Set up test database before running tests"""
    # Import all models to ensure they're registered with Base
    from app.models import Client, Employer, Employment, TerminationEvent
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    # Override dependency
    app.dependency_overrides[get_db] = override_get_db


def teardown_module(_module):
    """Clean up test database after running tests"""
    Base.metadata.drop_all(bind=engine)
    # Clear dependency overrides
    app.dependency_overrides.clear()


class TestClientAPI(unittest.TestCase):
    """Integration tests for FastAPI client CRUD endpoints"""

    def setUp(self):
        """Set up test database and client before each test"""
        # Override dependency to use test database
        app.dependency_overrides[get_db] = override_get_db
        
        # Ensure all tables exist
        Base.metadata.create_all(bind=engine)
        
        # Clean all data from tables but keep structure
        db = TestingSessionLocal()
        try:
            # Delete in correct order to avoid foreign key constraints
            db.query(TerminationEvent).delete()
            db.query(Employment).delete()
            db.query(Employer).delete()
            db.query(Client).delete()
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"Warning: Failed to clean database: {e}")
        finally:
            db.close()
        
        self.client = TestClient(app)
        
        # Use a valid Israeli ID number that passes validation
        # Generate unique ID and email to avoid conflicts between tests
        import random
        import time
        # Generate unique ID based on timestamp to ensure no conflicts
        timestamp = int(time.time() * 1000) % 100000  # Last 5 digits of timestamp
        # Use different valid ID numbers for different test runs
        valid_ids = ["111111118", "222222226", "333333334", "444444442"]
        self.unique_id = valid_ids[timestamp % len(valid_ids)]
        unique_email = f"test{random.randint(1000, 9999)}@example.com"
        
        # Sample valid client data
        self.valid_client_data = {
            "id_number_raw": self.unique_id,
            "full_name": "ישראל ישראלי",
            "first_name": "ישראל",
            "last_name": "ישראלי",
            "birth_date": (date.today() - timedelta(days=30*365)).isoformat(),  # 30 years ago
            "gender": "male",
            "marital_status": "single",
            "self_employed": False,
            "current_employer_exists": True,
            "planned_termination_date": (date.today() + timedelta(days=365)).isoformat(),  # 1 year from now
            "email": unique_email,
            "phone": "050-1234567",
            "address_street": "רחוב הרצל 1",
            "address_city": "תל אביב",
            "address_postal_code": "12345",
            "retirement_target_date": (date.today() + timedelta(days=35*365)).isoformat(),  # 35 years from now
            "is_active": True,
            "notes": "הערות לקוח"
        }

    def tearDown(self):
        """Clean up after each test"""
        # Drop all tables in the test database
        Base.metadata.drop_all(bind=engine)
        # Dispose of all connections
        engine.dispose()

    def test_create_client(self):
        """Test POST /api/v1/clients endpoint"""
        # Test creating a client with valid data
        response = self.client.post("/api/v1/clients", json=self.valid_client_data)
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIn("id", data)
        self.assertEqual(data["id_number"], self.unique_id)
        self.assertEqual(data["full_name"], "ישראל ישראלי")
        
        # Test creating a client with invalid ID number
        invalid_id_data = self.valid_client_data.copy()
        invalid_id_data["id_number_raw"] = "123456789"  # Invalid checksum
        response = self.client.post("/api/v1/clients", json=invalid_id_data)
        self.assertEqual(response.status_code, 422)
        self.assertIn("detail", response.json())
        
        # Test creating a client with invalid birth date (too young)
        invalid_birth_date_data = self.valid_client_data.copy()
        invalid_birth_date_data["birth_date"] = (date.today() - timedelta(days=17*365)).isoformat()  # 17 years old
        response = self.client.post("/api/v1/clients", json=invalid_birth_date_data)
        self.assertEqual(response.status_code, 422)
        self.assertIn("detail", response.json())
        
        # Test creating a client with duplicate ID number
        response = self.client.post("/api/v1/clients", json=self.valid_client_data)
        self.assertEqual(response.status_code, 409)  # Conflict
        self.assertIn("detail", response.json())

    def test_get_client(self):
        """Test GET /api/v1/clients/{id} endpoint"""
        # Create a client first
        create_response = self.client.post("/api/v1/clients", json=self.valid_client_data)
        self.assertEqual(create_response.status_code, 201)
        client_id = create_response.json()["id"]
        
        # Test getting the client by ID
        response = self.client.get(f"/api/v1/clients/{client_id}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], client_id)
        self.assertEqual(data["id_number"], self.unique_id)
        self.assertEqual(data["full_name"], "ישראל ישראלי")
        
        # Test getting a non-existent client
        response = self.client.get("/api/v1/clients/999999")
        self.assertEqual(response.status_code, 404)
        self.assertIn("detail", response.json())

    def test_update_client(self):
        """Test PATCH /api/v1/clients/{id} endpoint"""
        # Create a client first
        create_response = self.client.post("/api/v1/clients", json=self.valid_client_data)
        self.assertEqual(create_response.status_code, 201)
        client_id = create_response.json()["id"]
        
        # Test partial update
        update_data = {
            "full_name": "ישראל כהן",
            "marital_status": "married",
            "notes": "הערות מעודכנות"
        }
        response = self.client.patch(f"/api/v1/clients/{client_id}", json=update_data)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["full_name"], "ישראל כהן")
        self.assertEqual(data["marital_status"], "married")
        self.assertEqual(data["notes"], "הערות מעודכנות")
        
        # Test update with invalid data
        invalid_update = {
            "birth_date": (date.today() - timedelta(days=121*365)).isoformat()  # 121 years old (too old)
        }
        response = self.client.patch(f"/api/v1/clients/{client_id}", json=invalid_update)
        self.assertEqual(response.status_code, 422)
        self.assertIn("detail", response.json())
        
        # Test updating a non-existent client
        response = self.client.patch("/api/v1/clients/999999", json=update_data)
        self.assertEqual(response.status_code, 404)
        self.assertIn("detail", response.json())

    def test_delete_client(self):
        """Test DELETE /api/v1/clients/{id} endpoint"""
        # Create a client first
        create_response = self.client.post("/api/v1/clients", json=self.valid_client_data)
        self.assertEqual(create_response.status_code, 201)
        client_id = create_response.json()["id"]
        
        # Test deleting the client
        response = self.client.delete(f"/api/v1/clients/{client_id}")
        self.assertEqual(response.status_code, 204)
        
        # Verify client is deleted
        get_response = self.client.get(f"/api/v1/clients/{client_id}")
        self.assertEqual(get_response.status_code, 404)
        
        # Test deleting a non-existent client
        response = self.client.delete("/api/v1/clients/999999")
        self.assertEqual(response.status_code, 404)
        self.assertIn("detail", response.json())

    def test_list_clients(self):
        """Test GET /api/v1/clients endpoint with filtering, pagination, and sorting"""
        # Create multiple clients with unique IDs
        client1 = self.valid_client_data.copy()
        client1["id_number_raw"] = "111111118"  # First valid ID
        client1["full_name"] = "אברהם לוי"
        client1["gender"] = "male"
        client1["is_active"] = True
        
        client2 = self.valid_client_data.copy()
        client2["id_number_raw"] = "222222226"  # Second valid ID
        client2["full_name"] = "שרה כהן"
        client2["gender"] = "female"
        client2["is_active"] = True
        
        client3 = self.valid_client_data.copy()
        client3["id_number_raw"] = "333333334"  # Third valid ID
        client3["full_name"] = "יעקב ישראלי"
        client3["gender"] = "male"
        client3["is_active"] = False
        
        self.client.post("/api/v1/clients", json=client1)
        self.client.post("/api/v1/clients", json=client2)
        self.client.post("/api/v1/clients", json=client3)
        
        # Test listing all clients
        response = self.client.get("/api/v1/clients")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["items"]), 3)
        self.assertEqual(data["total"], 3)
        
        # Test filtering by active status
        response = self.client.get("/api/v1/clients?is_active=true")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["items"]), 2)
        self.assertEqual(data["total"], 2)
        
        # Test filtering by gender
        response = self.client.get("/api/v1/clients?gender=female")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["items"][0]["full_name"], "שרה כהן")
        
        # Test pagination
        response = self.client.get("/api/v1/clients?skip=1&limit=1")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["total"], 3)
        
        # Test sorting
        response = self.client.get("/api/v1/clients?sort=full_name")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["items"][0]["full_name"], "אברהם לוי")  # Hebrew alphabetical order
        
        # Test search
        response = self.client.get("/api/v1/clients?search=כהן")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["items"][0]["full_name"], "שרה כהן")


if __name__ == "__main__":
    unittest.main()
