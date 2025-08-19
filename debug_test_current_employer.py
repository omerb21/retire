"""
Manually test the current employer endpoint with our fixes
"""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from datetime import date

from app.main import app
from app.database import Base, get_db
from app.models.client import Client
from app.models.current_employer import CurrentEmployer

# Create a test database in memory
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
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

app.dependency_overrides[get_db] = override_get_db

# Create a test client
client = TestClient(app)

def setup_test_data():
    """Create a test client in the database"""
    db = TestingSessionLocal()
    try:
        print("Creating test client...")
        test_client = Client(
            id_number_raw="test123",
            id_number="test123",
            full_name="Test Client",
            birth_date=date(1980, 1, 1),
            is_active=True
        )
        db.add(test_client)
        db.commit()
        db.refresh(test_client)
        
        client_id = test_client.id
        print(f"Created test client with ID: {client_id}")
        
        # Verify client exists in a new session
        verify_db = TestingSessionLocal()
        try:
            found = verify_db.query(Client).filter(Client.id == client_id).first()
            print(f"Verification query - client found: {found is not None}")
            if found:
                print(f"Verified client details: ID={found.id}, Name={found.full_name}")
        finally:
            verify_db.close()
            
        return client_id
    finally:
        db.close()

def run_test_no_employer():
    """Test the 'client exists but has no current employer' scenario"""
    client_id = setup_test_data()
    
    print("\n--- Testing 'No Current Employer' Scenario ---")
    print(f"Making API request for client ID: {client_id}")
    
    response = client.get(f"/api/v1/clients/{client_id}/current-employer")
    
    print(f"Response status code: {response.status_code}")
    print(f"Response body: {response.json()}")
    
    # Check the response
    if response.status_code == 404 and response.json()["detail"]["error"] == "אין מעסיק נוכחי רשום ללקוח":
        print("TEST PASSED: Correct error message for client without current employer")
        return True
    else:
        print(f"TEST FAILED: Expected 404 with 'אין מעסיק נוכחי רשום ללקוח' but got {response.status_code} with {response.json()}")
        return False

if __name__ == "__main__":
    print("=== Running Manual Test of Current Employer Endpoint ===")
    success = run_test_no_employer()
    
    if success:
        print("\nAll tests passed!")
    else:
        print("\nTests failed!")
