"""
Tests for employment service functionality
"""
import unittest
from datetime import date, datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Client, Employer, Employment, TerminationEvent, TerminationReason
from app.services.employment_service import EmploymentService

def utcnow():
    return datetime.now(timezone.utc)

# Create test database for testing
TEST_DB_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DB_URL, 
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def make_client(id_number_raw=None, full_name="ישראל ישראלי", is_active=True):
    """Factory function to create a test client with all required fields"""
    import random
    from tests.utils import gen_valid_id
    if id_number_raw is None:
        # Generate unique valid Israeli ID for each test
        id_number_raw = gen_valid_id()
    
    return Client(
        id_number_raw=id_number_raw,
        id_number=id_number_raw,
        full_name=full_name,
        first_name="ישראל",
        last_name="ישראלי",
        birth_date=date(1980, 1, 1),
        is_active=is_active,
        email=f"test{random.randint(1000, 9999)}@example.com",
        phone="050-1234567",
        created_at=utcnow(),
        updated_at=utcnow()
    )

def setup_module(_module):
    """Set up test database before running tests"""
    # Import all models to ensure they're registered with Base
    from app.models import Client, Employer, Employment, TerminationEvent
    
    # Create all tables
    Base.metadata.create_all(bind=engine)

def teardown_module(_module):
    """Clean up test database after running tests"""
    Base.metadata.drop_all(bind=engine)

class TestEmploymentService(unittest.TestCase):
    """Tests for employment service functionality"""

    def setUp(self):
        """Set up test database and client before each test"""
        # Import all models to ensure they're registered with Base
        from app.models import Client, Employer, Employment, TerminationEvent
        
        # Create tables if they don't exist
        Base.metadata.create_all(bind=engine)
        
        self.db = TestingSessionLocal()
        
        # Create a test client in the database
        self.test_client = make_client()
        self.db.add(self.test_client)
        self.db.commit()
        self.client_id = self.test_client.id

    def tearDown(self):
        """Clean up after each test"""
        self.db.rollback()
        self.db.close()

    def test_set_current_employer_creates_new_employer_and_employment(self):
        """Test creating new employer and employment for active client"""
        # Act
        employment = EmploymentService.set_current_employer(
            db=self.db,
            client_id=self.client_id,
            employer_name="חברת טסט בע\"מ",
            reg_no="123456789",
            start_date=date(2023, 1, 1),
            monthly_salary_nominal=10000.0
        )
        
        # Assert
        self.assertIsNotNone(employment)
        self.assertEqual(employment.client_id, self.client_id)
        self.assertTrue(employment.is_current)
        self.assertEqual(employment.start_date, date(2023, 1, 1))
        self.assertEqual(employment.monthly_salary_nominal, 10000.0)
        
        # Check employer was created
        employer = self.db.get(Employer, employment.employer_id)
        self.assertEqual(employer.name, "חברת טסט בע\"מ")
        self.assertEqual(employer.reg_no, "123456789")

    def test_set_current_employer_reuses_existing_employer_by_reg_no(self):
        """Test reusing existing employer when reg_no matches"""
        # Arrange - create existing employer
        existing_employer = Employer(name="חברה ישנה", reg_no="123456789")
        self.db.add(existing_employer)
        self.db.commit()
        
        # Act
        employment = EmploymentService.set_current_employer(
            db=self.db,
            client_id=self.client_id,
            employer_name="חברת טסט בע\"מ",  # Different name
            reg_no="123456789",  # Same reg_no
            start_date=date(2023, 1, 1)
        )
        
        # Assert - should reuse existing employer
        self.assertEqual(employment.employer_id, existing_employer.id)
        
        # Check that employer name wasn't changed
        employer = self.db.get(Employer, employment.employer_id)
        self.assertEqual(employer.name, "חברה ישנה")

    def test_set_current_employer_closes_previous_employment(self):
        """Test that setting new employer closes previous current employment"""
        # Arrange - create first employment
        first_employment = EmploymentService.set_current_employer(
            db=self.db,
            client_id=self.client_id,
            employer_name="מעסיק ראשון",
            reg_no=None,
            start_date=date(2022, 1, 1)
        )
        self.db.commit()
        
        # Act - create second employment
        second_employment = EmploymentService.set_current_employer(
            db=self.db,
            client_id=self.client_id,
            employer_name="מעסיק שני",
            reg_no=None,
            start_date=date(2023, 1, 1)
        )
        
        # Assert
        self.db.refresh(first_employment)
        self.assertFalse(first_employment.is_current)
        self.assertTrue(second_employment.is_current)

    def test_set_current_employer_fails_for_inactive_client(self):
        """Test that setting employer fails for inactive client"""
        # Arrange - create inactive client
        inactive_client = make_client(id_number_raw="987654321", is_active=False)
        self.db.add(inactive_client)
        self.db.commit()
        
        # Act & Assert
        with self.assertRaises(ValueError) as context:
            EmploymentService.set_current_employer(
                db=self.db,
                client_id=inactive_client.id,
                employer_name="חברת טסט",
                reg_no=None,
                start_date=date(2023, 1, 1)
            )
        
        self.assertIn("לקוח לא קיים או לא פעיל", str(context.exception))

    def test_plan_termination_creates_termination_event(self):
        """Test planning termination for client with current employment"""
        # Arrange - create current employment
        employment = EmploymentService.set_current_employer(
            db=self.db,
            client_id=self.client_id,
            employer_name="חברת טסט",
            reg_no=None,
            start_date=date(2023, 1, 1)
        )
        self.db.commit()
        
        # Act
        termination_event = EmploymentService.plan_termination(
            db=self.db,
            client_id=self.client_id,
            planned_date=date(2023, 12, 31),
            reason=TerminationReason.retired
        )
        
        # Assert
        self.assertIsNotNone(termination_event)
        self.assertEqual(termination_event.client_id, self.client_id)
        self.assertEqual(termination_event.employment_id, employment.id)
        self.assertEqual(termination_event.planned_termination_date, date(2023, 12, 31))
        self.assertEqual(termination_event.reason, TerminationReason.retired)
        self.assertIsNone(termination_event.actual_termination_date)

    def test_plan_termination_fails_without_current_employment(self):
        """Test that planning termination fails when no current employment exists"""
        # Act & Assert
        with self.assertRaises(ValueError) as context:
            EmploymentService.plan_termination(
                db=self.db,
                client_id=self.client_id,
                planned_date=date(2023, 12, 31)
            )
        
        self.assertIn("אין מעסיק נוכחי ללקוח", str(context.exception))

    def test_confirm_termination_updates_employment_and_creates_event(self):
        """Test confirming termination updates employment and creates termination event"""
        # Arrange - create current employment
        employment = EmploymentService.set_current_employer(
            db=self.db,
            client_id=self.client_id,
            employer_name="חברת טסט",
            reg_no=None,
            start_date=date(2023, 1, 1)
        )
        self.db.commit()
        
        # Act
        termination_event = EmploymentService.confirm_termination(
            db=self.db,
            client_id=self.client_id,
            actual_date=date(2023, 6, 30),
            severance_basis_nominal=15000.0,
            reason=TerminationReason.resigned
        )
        
        # Assert termination event
        self.assertIsNotNone(termination_event)
        self.assertEqual(termination_event.client_id, self.client_id)
        self.assertEqual(termination_event.employment_id, employment.id)
        self.assertEqual(termination_event.actual_termination_date, date(2023, 6, 30))
        self.assertEqual(termination_event.severance_basis_nominal, 15000.0)
        self.assertEqual(termination_event.reason, TerminationReason.resigned)
        
        # Assert employment was updated
        self.db.refresh(employment)
        self.assertFalse(employment.is_current)
        self.assertEqual(employment.end_date, date(2023, 6, 30))

    def test_confirm_termination_fails_without_current_employment(self):
        """Test that confirming termination fails when no current employment exists"""
        # Act & Assert
        with self.assertRaises(ValueError) as context:
            EmploymentService.confirm_termination(
                db=self.db,
                client_id=self.client_id,
                actual_date=date(2023, 6, 30)
            )
        
        self.assertIn("אין מעסיק נוכחי ללקוח", str(context.exception))

    def test_business_scenario_no_current_employer(self):
        """Test business scenario: client without current employer"""
        # Both plan and confirm should fail
        with self.assertRaises(ValueError):
            EmploymentService.plan_termination(
                db=self.db,
                client_id=self.client_id,
                planned_date=date(2023, 12, 31)
            )
        
        with self.assertRaises(ValueError):
            EmploymentService.confirm_termination(
                db=self.db,
                client_id=self.client_id,
                actual_date=date(2023, 6, 30)
            )

    def test_business_scenario_retirement_age_with_employer(self):
        """Test business scenario: over retirement age with current employer"""
        # Arrange - create employment for older client
        employment = EmploymentService.set_current_employer(
            db=self.db,
            client_id=self.client_id,
            employer_name="חברת פרישה",
            reg_no=None,
            start_date=date(2020, 1, 1)
        )
        self.db.commit()
        
        # Act - should be able to confirm termination without planning
        termination_event = EmploymentService.confirm_termination(
            db=self.db,
            client_id=self.client_id,
            actual_date=date(2023, 6, 30),
            reason=TerminationReason.retired
        )
        
        # Assert - should succeed
        self.assertIsNotNone(termination_event)
        self.assertEqual(termination_event.reason, TerminationReason.retired)

if __name__ == '__main__':
    unittest.main()
