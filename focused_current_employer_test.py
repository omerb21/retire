"""
Focused test script that isolates the current employer endpoint test 
without using pytest or the test database setup.
"""
import os
import sys
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker
from datetime import date
import traceback

# Import the necessary modules from our app
from app.main import app
from app.database import Base, get_db
from app.models.client import Client
from app.models.current_employer import CurrentEmployer

# Set up a dedicated test database with a unique file
TEST_DB_FILE = "focused_test.db"
if os.path.exists(TEST_DB_FILE):
    os.remove(TEST_DB_FILE)
    
DB_URL = f"sqlite:///{TEST_DB_FILE}"
engine = create_engine(DB_URL, connect_args={"check_same_thread": False}, echo=True)
TestSessionLocal = sessionmaker(autoflush=True, expire_on_commit=False, bind=engine)

# Create all tables
Base.metadata.create_all(bind=engine)

# Override the FastAPI dependency
def override_get_db():
    db = TestSessionLocal()
    print(f"Creating session: {id(db)}")
    try:
        yield db
    finally:
        db.close()
        print(f"Closed session: {id(db)}")

# Apply the override
app.dependency_overrides[get_db] = override_get_db

# Create test client
test_client = TestClient(app)

def ensure_clean_db():
    """Make sure we start with a clean database"""
    with engine.connect() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(text(f"DELETE FROM {table.name}"))
        conn.commit()

def test_current_employer():
    """Test the current employer endpoint"""
    # Start with a clean database
    ensure_clean_db()
    
    try:
        # Step 1: Create a client
        db = TestSessionLocal()
        print("\n=== Step 1: Creating test client ===")
        client = Client(
            id_number_raw="focused_test_123",
            id_number="focused_test_123",
            full_name="Focused Test Client",
            birth_date=date(1990, 1, 1),
            is_active=True
        )
        db.add(client)
        db.commit()
        db.refresh(client)
        client_id = client.id
        print(f"Created client ID: {client_id}")
        db.close()
        
        # Step 2: Verify the client exists in the database
        db = TestSessionLocal()
        print("\n=== Step 2: Verifying client exists ===")
        found = db.query(Client).filter(Client.id == client_id).first()
        if not found:
            print("ERROR: Client not found in verification query!")
            return False
        print(f"Client verified: ID={found.id}, Name={found.full_name}")
        
        # Step 3: Ensure no current employer exists
        print("\n=== Step 3: Checking/removing any current employer ===")
        ce = db.scalar(select(CurrentEmployer).where(CurrentEmployer.client_id == client_id))
        if ce:
            print(f"Found current employer - removing it")
            db.delete(ce)
            db.commit()
        else:
            print("No current employer found - good!")
        db.close()
        
        # Step 4: Call the API endpoint
        print("\n=== Step 4: Calling API endpoint ===")
        endpoint = f"/api/v1/clients/{client_id}/current-employer"
        print(f"GET {endpoint}")
        response = test_client.get(endpoint)
        
        # Step 5: Validate the response
        print("\n=== Step 5: Validating response ===")
        print(f"Status code: {response.status_code}")
        print(f"Response body: {response.text}")
        
        expected_status = 404
        expected_error = "אין מעסיק נוכחי רשום ללקוח"
        
        if response.status_code == expected_status:
            try:
                response_json = response.json()
                if "detail" in response_json and "error" in response_json["detail"]:
                    actual_error = response_json["detail"]["error"]
                    if actual_error == expected_error:
                        print("\n✅ SUCCESS: Got expected error message!")
                        return True
                    else:
                        print(f"\n❌ FAILED: Got wrong error message.")
                        print(f"  Expected: '{expected_error}'")
                        print(f"  Actual: '{actual_error}'")
                        return False
                else:
                    print("\n❌ FAILED: Response JSON doesn't have expected structure")
                    return False
            except Exception as e:
                print(f"\n❌ FAILED: Couldn't parse response JSON: {e}")
                return False
        else:
            print(f"\n❌ FAILED: Got status code {response.status_code} instead of {expected_status}")
            return False
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("\n=== RUNNING FOCUSED TEST OF CURRENT EMPLOYER ENDPOINT ===")
    success = test_current_employer()
    if success:
        print("\n=== TEST PASSED ===")
        sys.exit(0)
    else:
        print("\n=== TEST FAILED ===")
        sys.exit(1)
