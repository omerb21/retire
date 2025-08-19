"""
Manual test script for current employer endpoint
"""
import sys
import os
from datetime import date
from fastapi.testclient import TestClient

# Add the current directory to the path so we can import app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.main import app
from app.database import SessionLocal
from app.models.client import Client

def test_current_employer_endpoint():
    """Test the current employer endpoint behavior"""
    print("=== Testing Current Employer Endpoint ===")
    
    client = TestClient(app)
    db = SessionLocal()
    
    try:
        # Test 1: Non-existent client
        print("\nTest 1: Non-existent client")
        response = client.get("/api/v1/clients/99999/current-employer")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        
        # Test 2: Create a client without current employer
        print("\nTest 2: Client exists but no current employer")
        
        # Create test client
        test_client = Client(
            id_number_raw="999888777",
            id_number="999888777", 
            full_name="Test Client No Employer",
            birth_date=date(1980, 1, 1),
            is_active=True
        )
        db.add(test_client)
        db.commit()
        db.refresh(test_client)
        
        print(f"Created client with ID: {test_client.id}")
        
        # Test the endpoint
        response = client.get(f"/api/v1/clients/{test_client.id}/current-employer")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        
        # Clean up
        db.delete(test_client)
        db.commit()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_current_employer_endpoint()
