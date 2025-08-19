"""
Debug script to understand the database session isolation issue
"""
import sys
import os
from datetime import date
from fastapi.testclient import TestClient

# Add the current directory to the path so we can import app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.main import app
from app.database import SessionLocal, get_db
from app.models.client import Client

def debug_session_isolation():
    """Debug the session isolation issue"""
    print("=== Debugging Session Isolation Issue ===")
    
    # Create a test client using the same session factory as the tests
    db = SessionLocal()
    
    try:
        # Create a test client
        test_client = Client(
            id_number_raw="debugclient123",
            id_number="debugclient123",
            full_name="Debug Client",
            birth_date=date(1985, 5, 15),
            is_active=True
        )
        db.add(test_client)
        db.commit()
        db.refresh(test_client)
        
        client_id = test_client.id
        print(f"Created test client with ID: {client_id}")
        
        # Verify the client exists in the same session
        found_client = db.query(Client).filter(Client.id == client_id).first()
        print(f"Client found in same session: {found_client is not None}")
        
        # Now test with a new session (simulating what the API does)
        db2 = SessionLocal()
        try:
            found_client2 = db2.query(Client).filter(Client.id == client_id).first()
            print(f"Client found in new session: {found_client2 is not None}")
            
            if found_client2:
                print(f"Client details: ID={found_client2.id}, name={found_client2.full_name}")
            else:
                print("Client not found in new session - this is the problem!")
                
        finally:
            db2.close()
        
        # Now test the actual API endpoint
        api_client = TestClient(app)
        response = api_client.get(f"/api/v1/clients/{client_id}/current-employer")
        
        print(f"API response status: {response.status_code}")
        print(f"API response: {response.json()}")
        
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
    debug_session_isolation()
