"""
Debug script to test scenario API and see error details
"""
import json
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database import get_db
from tests.conftest import get_test_db
from app.models.client import Client
from app.models.employment import Employment
from app.models.employer import Employer
from tests.utils import gen_valid_id, gen_reg_no

# Override the dependency
app.dependency_overrides[get_db] = get_test_db

client = TestClient(app)

def make_client():
    """Create a test client with valid data"""
    id_num = gen_valid_id()
    return Client(
        id_number=id_num,
        id_number_raw=id_num,
        full_name="יוסי כהן",
        first_name="יוסי",
        last_name="כהן",
        birth_date=date(1980, 1, 1),
        address_city="תל אביב",
        address_street="רחוב הרצל 123",
        address_postal_code="12345",
        phone="050-1234567",
        email="test@example.com",
        is_active=True
    )

def make_employer():
    """Create a test employer with valid data"""
    return Employer(
        name="חברת טסט בע\"מ",
        reg_no=gen_reg_no()
    )

def make_employment(client_id: int, employer_id: int):
    """Create a test employment with valid data"""
    return Employment(
        client_id=client_id,
        employer_id=employer_id,
        start_date=date(2020, 1, 1),
        monthly_salary_nominal=15000.0,
        is_current=True
    )

def debug_scenario_creation():
    """Debug scenario creation and running"""
    # Get test database session
    db_session = next(get_test_db())
    
    try:
        # Create test client
        test_client = make_client()
        db_session.add(test_client)
        db_session.commit()
        print(f"Created client with ID: {test_client.id}")
        
        # Create employer
        employer = make_employer()
        db_session.add(employer)
        db_session.commit()
        print(f"Created employer with ID: {employer.id}")
        
        # Create employment
        employment = make_employment(test_client.id, employer.id)
        db_session.add(employment)
        db_session.commit()
        print(f"Created employment with ID: {employment.id}")
        
        # Create scenario
        scenario_data = {
            "scenario_name": "תרחיש בדיקה",
            "planned_termination_date": "2024-12-31",
            "monthly_expenses": 8000.0,
            "apply_tax_planning": True,
            "apply_capitalization": False,
            "apply_exemption_shield": True,
            "other_parameters": {"test_param": "test_value"}
        }
        
        print(f"Creating scenario for client {test_client.id}...")
        response = client.post(f"/api/v1/clients/{test_client.id}/scenarios", json=scenario_data)
        print(f"Create scenario response: {response.status_code}")
        print(f"Create scenario response body: {response.json()}")
        
        if response.status_code == 201:
            scenario_id = response.json()["scenario_id"]
            print(f"Created scenario with ID: {scenario_id}")
            
            # Run scenario
            print(f"Running scenario {scenario_id}...")
            run_response = client.post(f"/api/v1/scenarios/{scenario_id}/run")
            print(f"Run scenario response: {run_response.status_code}")
            print(f"Run scenario response body: {run_response.json()}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db_session.close()

if __name__ == "__main__":
    debug_scenario_creation()
