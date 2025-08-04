"""
Integration tests for employment API endpoints
"""
import unittest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, StaticPool
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import get_db, Base
from app.models import Client, Employer, Employment, TerminationEvent, TerminationReason
from app.services.client_service import normalise_and_validate_id_number


class TestEmploymentAPI(unittest.TestCase):
    
    def setUp(self):
        """Set up test database and client"""
        # Create in-memory SQLite database with StaticPool
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        
        # Import all models before creating tables
        from app.models import Client, Employer, Employment, TerminationEvent
        
        # Create all tables
        Base.metadata.create_all(bind=self.engine)
        
        # Create session
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db = TestingSessionLocal()
        
        # Override dependency
        def override_get_db():
            try:
                yield self.db
            finally:
                pass  # Don't close here, we'll handle it in tearDown
        
        app.dependency_overrides[get_db] = override_get_db
        
        # Create test client
        self.client = TestClient(app)
        
        # Create test client in database with unique ID
        from tests.utils import gen_valid_id
        import random
        
        # Generate unique valid Israeli ID for this test
        raw_id = gen_valid_id()
        self.test_client_data = {
            "id_number_raw": raw_id,
            "full_name": "ישראל ישראלי",
            "birth_date": "1980-01-01",
            "email": f"test_{self.id()}_{random.randint(1000, 9999)}@example.com",  # Unique email per test
            "phone": "0501234567",
            "address_city": "תל אביב",
            "address_street": "רחוב הברוש 5",
            "address_postal_code": "6100000"
        }
        
        response = self.client.post("/api/v1/clients", json=self.test_client_data)
        self.assertEqual(response.status_code, 201)
        self.test_client_id = response.json()["id"]
    
    def tearDown(self):
        """Clean up test database"""
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        app.dependency_overrides.clear()
    
    def test_set_current_employer_201(self):
        """Test creating current employment returns 201 with valid EmploymentOut structure"""
        employment_data = {
            "employer_name": "חברת הטכנולוגיה בע\"מ",
            "employer_reg_no": "123456789",
            "address_city": "תל אביב",
            "address_street": "רחוב הארבעה 10",
            "start_date": "2023-01-01"
        }
        
        response = self.client.post(
            f"/api/v1/clients/{self.test_client_id}/employment/current",
            json=employment_data
        )
        
        self.assertEqual(response.status_code, 201)
        
        data = response.json()
        self.assertIn("id", data)
        self.assertEqual(data["client_id"], self.test_client_id)
        self.assertIn("employer_id", data)
        self.assertEqual(data["start_date"], "2023-01-01")
        self.assertIsNone(data["end_date"])
        self.assertTrue(data["is_current"])
        self.assertIn("created_at", data)
        self.assertIn("updated_at", data)
    
    def test_plan_termination_200(self):
        """Test planning termination after current employer returns 200 with TerminationEventOut"""
        # First, set current employer
        employment_data = {
            "employer_name": "חברת הטכנולוגיה בע\"מ",
            "employer_reg_no": "123456789",
            "address_city": "תל אביב",
            "address_street": "רחוב הארבעה 10",
            "start_date": "2023-01-01"
        }
        
        response = self.client.post(
            f"/api/v1/clients/{self.test_client_id}/employment/current",
            json=employment_data
        )
        self.assertEqual(response.status_code, 201)
        
        # Now plan termination
        planned_date = date.today() + timedelta(days=30)
        termination_data = {
            "planned_termination_date": planned_date.isoformat(),
            "termination_reason": TerminationReason.retired.value
        }
        
        response = self.client.patch(
            f"/api/v1/clients/{self.test_client_id}/employment/termination/plan",
            json=termination_data
        )
        
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn("id", data)
        self.assertEqual(data["client_id"], self.test_client_id)
        self.assertIn("employment_id", data)
        self.assertEqual(data["reason"], TerminationReason.retired.value)
        self.assertEqual(data["planned_termination_date"], planned_date.isoformat())
        self.assertIsNone(data["actual_termination_date"])
        self.assertIn("created_at", data)
        self.assertIn("updated_at", data)
    
    def test_confirm_termination_200_triggers_fixation_background(self):
        """Test confirming termination returns 200 and doesn't fail if fixation modules unavailable"""
        # First, set current employer
        employment_data = {
            "employer_name": "חברת הטכנולוגיה בע\"מ",
            "employer_reg_no": "123456789",
            "address_city": "תל אביב",
            "address_street": "רחוב הארבעה 10",
            "start_date": "2023-01-01"
        }
        
        response = self.client.post(
            f"/api/v1/clients/{self.test_client_id}/employment/current",
            json=employment_data
        )
        self.assertEqual(response.status_code, 201)
        
        # Plan termination
        planned_date = date.today() + timedelta(days=30)
        termination_data = {
            "planned_termination_date": planned_date.isoformat(),
            "termination_reason": TerminationReason.retired.value
        }
        
        response = self.client.patch(
            f"/api/v1/clients/{self.test_client_id}/employment/termination/plan",
            json=termination_data
        )
        self.assertEqual(response.status_code, 200)
        
        # Confirm termination
        actual_date = date.today()
        confirm_data = {
            "actual_termination_date": actual_date.isoformat()
        }
        
        response = self.client.post(
            f"/api/v1/clients/{self.test_client_id}/employment/termination/confirm",
            json=confirm_data
        )
        
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn("id", data)
        self.assertEqual(data["client_id"], self.test_client_id)
        self.assertIn("employment_id", data)
        self.assertEqual(data["reason"], TerminationReason.retired.value)
        self.assertEqual(data["planned_termination_date"], planned_date.isoformat())
        self.assertEqual(data["actual_termination_date"], actual_date.isoformat())
        self.assertIn("created_at", data)
        self.assertIn("updated_at", data)
    
    def test_plan_without_current_409(self):
        """Test planning termination without current employment returns 409 with Hebrew error"""
        planned_date = date.today() + timedelta(days=30)
        termination_data = {
            "planned_termination_date": planned_date.isoformat(),
            "termination_reason": TerminationReason.retired.value
        }
        
        response = self.client.patch(
            f"/api/v1/clients/{self.test_client_id}/employment/termination/plan",
            json=termination_data
        )
        
        self.assertEqual(response.status_code, 409)
        
        data = response.json()
        self.assertIn("detail", data)
        self.assertIn("error", data["detail"])
        # Verify Hebrew error message
        self.assertIn("לא ניתן לתכנן עזיבה", data["detail"]["error"])
    
    def test_set_current_employer_idempotent_or_conflict(self):
        """Test setting current employer when one already exists"""
        # First employment
        employment_data_1 = {
            "employer_name": "חברת הטכנולוגיה בע\"מ",
            "employer_reg_no": "123456789",
            "address_city": "תל אביב",
            "address_street": "רחוב הארבעה 10",
            "start_date": "2023-01-01"
        }
        
        response = self.client.post(
            f"/api/v1/clients/{self.test_client_id}/employment/current",
            json=employment_data_1
        )
        self.assertEqual(response.status_code, 201)
        
        # Second employment (should handle according to service logic)
        employment_data_2 = {
            "employer_name": "חברה חדשה בע\"מ",
            "employer_reg_no": "987654321",
            "address_city": "חיפה",
            "address_street": "רחוב הגפן 5",
            "start_date": "2024-01-01"
        }
        
        response = self.client.post(
            f"/api/v1/clients/{self.test_client_id}/employment/current",
            json=employment_data_2
        )
        
        # Should either succeed (201/200) if service allows update, or conflict (409)
        self.assertIn(response.status_code, [200, 201, 409])
        
        if response.status_code == 409:
            # Verify Hebrew error message
            data = response.json()
            self.assertIn("detail", data)
            self.assertIn("error", data["detail"])
            self.assertIn("לא ניתן לעדכן מעסיק נוכחי", data["detail"]["error"])
    
    def test_plan_termination_past_date_422(self):
        """Test planning termination with past date returns 422"""
        # First, set current employer
        employment_data = {
            "employer_name": "חברת הטכנולוגיה בע\"מ",
            "employer_reg_no": "123456789",
            "address_city": "תל אביב",
            "address_street": "רחוב הארבעה 10",
            "start_date": "2023-01-01"
        }
        
        response = self.client.post(
            f"/api/v1/clients/{self.test_client_id}/employment/current",
            json=employment_data
        )
        self.assertEqual(response.status_code, 201)
        
        # Try to plan termination with past date
        past_date = date.today() - timedelta(days=1)
        termination_data = {
            "planned_termination_date": past_date.isoformat(),
            "termination_reason": TerminationReason.retired.value
        }
        
        response = self.client.patch(
            f"/api/v1/clients/{self.test_client_id}/employment/termination/plan",
            json=termination_data
        )
        
        self.assertEqual(response.status_code, 422)
        
        data = response.json()
        self.assertIn("detail", data)
        self.assertIn("error", data["detail"])
        self.assertIn("תאריך עזיבה מתוכנן חייב להיות היום או בעתיד", data["detail"]["error"])
    
    def test_invalid_termination_reason(self):
        """Test planning termination with invalid reason"""
        # First, set current employer
        employment_data = {
            "employer_name": "חברת הטכנולוגיה בע\"מ",
            "employer_reg_no": "123456789",
            "address_city": "תל אביב",
            "address_street": "רחוב הארבעה 10",
            "start_date": "2023-01-01"
        }
        
        response = self.client.post(
            f"/api/v1/clients/{self.test_client_id}/employment/current",
            json=employment_data
        )
        self.assertEqual(response.status_code, 201)
        
        # Try to plan termination with invalid reason
        planned_date = date.today() + timedelta(days=30)
        termination_data = {
            "planned_termination_date": planned_date.isoformat(),
            "termination_reason": "INVALID_REASON"
        }
        
        response = self.client.patch(
            f"/api/v1/clients/{self.test_client_id}/employment/termination/plan",
            json=termination_data
        )
        
        # Should return 409 or 422 depending on service validation
        self.assertIn(response.status_code, [409, 422])
    
    def test_nonexistent_client_404(self):
        """Test operations on nonexistent client return 404 with Hebrew error"""
        nonexistent_client_id = 99999
        
        employment_data = {
            "employer_name": "חברת הטכנולוגיה בע\"מ",
            "employer_reg_no": "123456789",
            "address_city": "תל אביב",
            "address_street": "רחוב הארבעה 10",
            "start_date": "2023-01-01"
        }
        
        response = self.client.post(
            f"/api/v1/clients/{nonexistent_client_id}/employment/current",
            json=employment_data
        )
        
        self.assertEqual(response.status_code, 404)
        
        data = response.json()
        self.assertIn("detail", data)
        self.assertIn("error", data["detail"])
        self.assertIn("לקוח לא נמצא במערכת", data["detail"]["error"])


if __name__ == "__main__":
    unittest.main()
