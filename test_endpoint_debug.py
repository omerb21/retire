"""
Debug script to test the current employer endpoint directly
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

def test_endpoint_directly():
    """Test the current employer endpoint directly"""
    print("=== Testing Current Employer Endpoint Directly ===")
    
    client_api = TestClient(app)
    db = SessionLocal()
    
    try:
        # Create a test client directly in the database
        test_client = Client(
            id_number_raw="testclient123",
            id_number="testclient123",
            full_name="Test Client for Endpoint",
            birth_date=date(1985, 5, 15),
            is_active=True
        )
        db.add(test_client)
        db.commit()
        db.refresh(test_client)
        
        client_id = test_client.id
        print(f"Created test client with ID: {client_id}")
        
        # Test the endpoint
        print(f"Testing GET /api/v1/clients/{client_id}/current-employer")
        response = client_api.get(f"/api/v1/clients/{client_id}/current-employer")
        
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.json()}")
        
        # Verify what we expect
        if response.status_code == 404:
            error_msg = response.json()["detail"]["error"]
            print(f"Error message: '{error_msg}'")
            
            if error_msg == "אין מעסיק נוכחי רשום ללקוח":
                print("✓ SUCCESS: Correct error message for client without employer")
                return True
            elif error_msg == "לקוח לא נמצא":
                print("✗ FAILED: Wrong error message - client should exist")
                return False
            else:
                print(f"✗ FAILED: Unexpected error message: {error_msg}")
                return False
        else:
            print(f"✗ FAILED: Expected 404, got {response.status_code}")
            return False
            
    except Exception as e:
        print(f"Exception: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up
        try:
            if 'test_client' in locals():
                db.delete(test_client)
                db.commit()
        except:
            pass
        db.close()

if __name__ == "__main__":
    test_endpoint_directly()
