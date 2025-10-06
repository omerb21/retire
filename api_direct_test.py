"""
Direct API test script that creates a client and immediately calls the current employer endpoint
to verify the proper error message is returned.

This is the most minimal test possible to validate the fix.
"""
import os
import sqlite3
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import date
import json

# Import necessary modules from app
from app.main import app
from app.database import Base, get_db
from app.models.client import Client
from app.models.current_employer import CurrentEmployer

# Create a test database
TEST_DB_FILE = "api_direct_test.db"
if os.path.exists(TEST_DB_FILE):
    os.remove(TEST_DB_FILE)

SQLALCHEMY_DATABASE_URL = f"sqlite:///{TEST_DB_FILE}"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autoflush=True, expire_on_commit=False, bind=engine)

# Create tables
Base.metadata.create_all(bind=engine)

# Override the get_db dependency
def override_get_db():
    db = TestingSessionLocal()
    print(f"\n>> Created API test session: {id(db)}")
    try:
        yield db
    finally:
        print(f">> Closing API test session: {id(db)}")
        db.close()

# Override the dependency
app.dependency_overrides[get_db] = override_get_db

# Create a test client
api_client = TestClient(app)

def run_test():
    print("\n===== DIRECT API TEST =====")
    
    # 1. Create a client directly with SQLAlchemy ORM
    print("\n1. Creating test client with SQLAlchemy...")
    db = TestingSessionLocal()
    try:
        test_client = Client(
            id_number_raw="direct_test_123",
            id_number="direct_test_123",
            full_name="Direct Test Client",
            birth_date=date(1990, 1, 1),
            is_active=True
        )
        db.add(test_client)
        db.commit()
        db.refresh(test_client)
        client_id = test_client.id
        print(f"   Created client with ID: {client_id}")
        
        # Verify client exists in same session
        check = db.query(Client).filter(Client.id == client_id).first()
        print(f"   Client verification (same session): {'✓' if check else '✗'}")
    finally:
        db.close()
    
    # 2. Verify client using raw SQL to ensure it's in the database
    print("\n2. Verifying client with raw SQL...")
    conn = sqlite3.connect(TEST_DB_FILE)
    cursor = conn.cursor()
    cursor.execute(f"SELECT id, id_number, full_name FROM client WHERE id = {client_id}")
    row = cursor.fetchone()
    if row:
        print(f"   ✓ Found in database: ID={row[0]}, ID Number={row[1]}, Name={row[2]}")
    else:
        print(f"   ✗ NOT found in database!")
        return False
    conn.close()
    
    # 3. Make API request to current employer endpoint
    print("\n3. Calling current employer API endpoint...")
    endpoint = f"/api/v1/clients/{client_id}/current-employer"
    print(f"   GET {endpoint}")
    response = api_client.get(endpoint)
    
    # 4. Check response
    print(f"\n4. API Response:")
    print(f"   Status code: {response.status_code}")
    try:
        response_json = response.json()
        print(f"   Response JSON: {json.dumps(response_json, indent=2, ensure_ascii=False)}")
        
        # 5. Verify expected error message
        expected_status = 404
        expected_error = "אין מעסיק נוכחי רשום ללקוח"  # No current employer registered for client
        
        if response.status_code == expected_status:
            if "detail" in response_json and "error" in response_json["detail"]:
                actual_error = response_json["detail"]["error"]
                if actual_error == expected_error:
                    print("\n✅ TEST PASSED: Got correct error message!")
                    return True
                else:
                    print(f"\n❌ TEST FAILED: Got wrong error message.")
                    print(f"   Expected: '{expected_error}'")
                    print(f"   Actual: '{actual_error}'")
                    return False
            else:
                print("\n❌ TEST FAILED: Response JSON doesn't have expected structure")
                return False
        else:
            print(f"\n❌ TEST FAILED: Got status code {response.status_code} instead of {expected_status}")
            return False
    except Exception as e:
        print(f"\n❌ ERROR: Could not parse response JSON: {e}")
        print(f"   Raw response: {response.text}")
        return False

if __name__ == "__main__":
    success = run_test()
    print("\n===========================")
    if success:
        print("✅ TEST PASSED: The API correctly returns 'no current employer' error")
        print("✅ THE FIX WORKED!")
    else:
        print("❌ TEST FAILED: The API is still not working correctly")
        print("❌ The issue persists!")
    print("===========================\n")
