"""
Debug script for CurrentEmployer API endpoints
"""
from fastapi.testclient import TestClient
from app.main import app
from app.models import Client
from app.database import get_db
from datetime import date

def debug_current_employer_api():
    client = TestClient(app)
    
    # Test if the endpoint exists
    print("Testing CurrentEmployer API endpoints...")
    
    # Test creating a client first
    try:
        # Get database session
        db = next(get_db())
        
        # Create a test client
        test_client = Client(
            id_number_raw="123456789",
            id_number="123456789",
            full_name="Debug Test Client",
            birth_date=date(1980, 1, 1),
            is_active=True
        )
        db.add(test_client)
        db.commit()
        db.refresh(test_client)
        client_id = test_client.id
        print(f"Created test client with ID: {client_id}")
        
        # Test creating current employer
        employer_data = {
            "employer_name": "Test Company",
            "start_date": "2020-01-01",
            "last_salary": 10000.0
        }
        
        print("Testing POST /api/v1/clients/{client_id}/employment/current")
        response = client.post(f"/api/v1/clients/{client_id}/employment/current", json=employer_data)
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.text}")
        
        if response.status_code != 201:
            print("ERROR: Expected 201, got", response.status_code)
            return False
        
        # Test getting current employer
        print("\nTesting GET /api/v1/clients/{client_id}/employment/current")
        get_response = client.get(f"/api/v1/clients/{client_id}/employment/current")
        print(f"GET Response status: {get_response.status_code}")
        print(f"GET Response body: {get_response.text}")
        
        if get_response.status_code != 200:
            print("ERROR: Expected 200, got", get_response.status_code)
            return False
        
        # Test adding grant
        grant_data = {
            "grant_type": "severance",
            "grant_amount": 50000.0,
            "grant_date": "2024-01-01"
        }
        
        print("\nTesting POST /api/v1/clients/{client_id}/employment/current/grants")
        grant_response = client.post(f"/api/v1/clients/{client_id}/employment/current/grants", json=grant_data)
        print(f"Grant Response status: {grant_response.status_code}")
        print(f"Grant Response body: {grant_response.text}")
        
        if grant_response.status_code != 201:
            print("ERROR: Expected 201, got", grant_response.status_code)
            return False
        
        print("\nAll tests passed!")
        return True
        
    except Exception as e:
        print(f"Exception occurred: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    debug_current_employer_api()
