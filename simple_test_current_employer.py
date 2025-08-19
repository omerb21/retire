"""
Simple stand-alone test for the current employer endpoint that doesn't rely on pytest
"""
import os
import sys
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from datetime import date

# Import the necessary modules from our app
from app.main import app
from app.database import Base, get_db
from app.models.client import Client
from app.models.current_employer import CurrentEmployer

# Create a test database file
db_file = "test_current_employer.db"
if os.path.exists(db_file):
    os.remove(db_file)

SQLALCHEMY_DATABASE_URL = f"sqlite:///{db_file}"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autoflush=True, expire_on_commit=False, bind=engine)

# Create tables
Base.metadata.create_all(bind=engine)

# Override the get_db dependency
def override_get_db():
    db = TestingSessionLocal()
    print(f"Created test DB session with ID: {id(db)}")
    try:
        yield db
    finally:
        db.close()

# Override the app's dependency
app.dependency_overrides[get_db] = override_get_db

# Create a test client
client = TestClient(app)

def run_test():
    print("=== Testing Current Employer API ===")
    
    # Create a test client
    db = TestingSessionLocal()
    try:
        print("\n1. Creating test client in database...")
        test_client = Client(
            id_number_raw="simple_test_123",
            id_number="simple_test_123",
            full_name="Simple Test Client",
            birth_date=date(1980, 1, 1),
            is_active=True
        )
        db.add(test_client)
        db.commit()
        db.refresh(test_client)
        client_id = test_client.id
        print(f"   Created client with ID: {client_id}")
        
        # Verify client exists
        print("\n2. Verifying client exists in database...")
        found_client = db.query(Client).filter(Client.id == client_id).first()
        if found_client:
            print(f"   ✓ Client found: ID={found_client.id}, Name={found_client.full_name}")
        else:
            print(f"   ✗ Client not found in database! Test will fail.")
            return False
            
        # Make sure no current employer exists
        print("\n3. Ensuring no current employer exists...")
        ce = db.scalar(select(CurrentEmployer).where(CurrentEmployer.client_id == client_id))
        if ce:
            print(f"   - Found existing current employer, deleting it")
            db.delete(ce)
            db.commit()
        else:
            print(f"   ✓ No current employer found - good!")
            
        # Make the API request
        print("\n4. Making API request to the endpoint...")
        print(f"   GET /api/v1/clients/{client_id}/current-employer")
        response = client.get(f"/api/v1/clients/{client_id}/current-employer")
        
        # Print response details
        print(f"\n5. API Response:")
        print(f"   Status code: {response.status_code}")
        try:
            response_json = response.json()
            print(f"   Response body: {response_json}")
            
            # Check for expected error message
            if response.status_code == 404 and response_json["detail"]["error"] == "אין מעסיק נוכחי רשום ללקוח":
                print("\n✅ TEST PASSED: Got the correct error message for client without current employer")
                return True
            else:
                print("\n❌ TEST FAILED: Didn't get the expected error message")
                if response.status_code == 404 and "detail" in response_json and "error" in response_json["detail"]:
                    print(f"   Got error: '{response_json['detail']['error']}' instead of 'אין מעסיק נוכחי רשום ללקוח'")
                return False
        except Exception as e:
            print(f"\n❌ TEST FAILED: Could not parse response JSON: {e}")
            print(f"   Raw response: {response.text}")
            return False
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()
        
if __name__ == "__main__":
    success = run_test()
    if success:
        print("\nTest completed successfully!")
        sys.exit(0)
    else:
        print("\nTest failed!")
        sys.exit(1)
