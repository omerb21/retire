import unittest
from datetime import date, datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import get_db, Base
from app.models.client import Client


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
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.rollback()  # Ensure any uncommitted changes are rolled back
        db.close()


app.dependency_overrides[get_db] = override_get_db


class TestClientAPI(unittest.TestCase):
    """Integration tests for FastAPI client CRUD endpoints"""

    def setUp(self):
        """Set up test database and client before each test"""
        # Drop and recreate tables to ensure clean state
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        
        # Clear any existing sessions
        engine.dispose()
        
        self.client = TestClient(app)
        
        # Sample valid client data
        self.valid_client_data = {
            "id_number_raw": "123456782",
            "full_name": "ישראל ישראלי",
            "first_name": "ישראל",
            "last_name": "ישראלי",
            "birth_date": (date.today() - timedelta(days=30*365)).isoformat(),  # 30 years ago
            "gender": "male",
            "marital_status": "single",
            "self_employed": False,
            "current_employer_exists": True,
            "planned_termination_date": (date.today() + timedelta(days=365)).isoformat(),  # 1 year from now
            "email": "user@example.com",
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

    def test_create_client(self):
        """Test POST /api/v1/clients endpoint"""
        # Test creating a client with valid data
        response = self.client.post("/api/v1/clients", json=self.valid_client_data)
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIn("id", data)
        self.assertEqual(data["id_number"], "123456782")
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
        self.assertEqual(data["id_number"], "123456782")
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
        # Create multiple clients
        client1 = self.valid_client_data.copy()
        client1["full_name"] = "אברהם לוי"
        client1["gender"] = "male"
        client1["is_active"] = True
        
        client2 = self.valid_client_data.copy()
        client2["id_number_raw"] = "305567663"  # Different valid ID
        client2["full_name"] = "שרה כהן"
        client2["gender"] = "female"
        client2["is_active"] = True
        
        client3 = self.valid_client_data.copy()
        client3["id_number_raw"] = "557845682"  # Different valid ID
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
