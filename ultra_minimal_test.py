"""
Ultra-minimal test script for the current employer endpoint.
This focuses only on the core issue without using pytest.
"""
import os
from fastapi import FastAPI, Depends, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker, Session

from app.models.client import Client
from app.models.current_employer import CurrentEmployer
from app.database import Base
from app.routers.current_employer import router as current_employer_router

# Create a simple test app
app = FastAPI()
app.include_router(current_employer_router, prefix="/api/v1")

# Create an in-memory database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///./ultra_minimal.db"
if os.path.exists("./ultra_minimal.db"):
    os.remove("./ultra_minimal.db")
    
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autoflush=True, expire_on_commit=False, bind=engine)
Base.metadata.create_all(bind=engine)

# Create db dependency
def get_test_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

# Import the get_db function from the app
from app.database import get_db

# Override the endpoint's db dependency
app.dependency_overrides[get_db] = get_test_db

# Create a test client
client = TestClient(app)

def setup_test_client():
    """Create a test client in the database and return its ID"""
    db = TestingSessionLocal()
    test_client = Client(
        id_number_raw="ultra_minimal_test",
        id_number="ultra_minimal_test",
        full_name="Ultra Minimal Test Client",
        birth_date="1990-01-01",
        is_active=True
    )
    db.add(test_client)
    db.commit()
    db.refresh(test_client)
    client_id = test_client.id
    print(f"Created test client with ID: {client_id}")
    
    # Verify client exists in a new session
    verify_db = TestingSessionLocal()
    found = verify_db.query(Client).filter(Client.id == client_id).first()
    print(f"Client found in verification query: {found is not None}")
    
    verify_db.close()
    db.close()
    return client_id

def test_no_current_employer():
    """Test the API endpoint with a client that has no current employer"""
    # Create a test client
    client_id = setup_test_client()
    
    # Call the API endpoint
    response = client.get(f"/api/v1/clients/{client_id}/current-employer")
    print(f"Response status: {response.status_code}")
    
    try:
        response_json = response.json()
        print(f"Response body: {response_json}")
        
        # Check for expected result
        if response.status_code == 404 and response_json["detail"]["error"] == "אין מעסיק נוכחי רשום ללקוח":
            print("TEST PASSED: Got correct error message")
            return True
        else:
            print("TEST FAILED: Didn't get expected error message")
            return False
    except Exception as e:
        print(f"Error parsing response: {e}")
        print(f"Raw response text: {response.text}")
        return False

if __name__ == "__main__":
    print("\n=== Running Ultra-Minimal Test ===")
    success = test_no_current_employer()
    if success:
        print("\n=== Test Passed ===")
    else:
        print("\n=== Test Failed ===")
