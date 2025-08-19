"""
Simple script to test the current employer endpoint directly
"""
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from datetime import date

from app.main import app
from app.database import Base, get_db
from app.models.client import Client
from app.models.current_employer import CurrentEmployer

# Create a test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_current_employer_debug.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autoflush=True, bind=engine)

# Create tables
Base.metadata.create_all(bind=engine)

# Override the get_db dependency
def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

# Create a test client
client = TestClient(app)

def setup_test_data():
    # Create a test client
    db = TestingSessionLocal()
    try:
        test_client = Client(
            id_number_raw="testdebug",
            id_number="testdebug",
            full_name="Test Debug Client",
            birth_date=date(1980, 1, 1),
            is_active=True
        )
        db.add(test_client)
        db.commit()
        db.refresh(test_client)
        client_id = test_client.id
        print(f"Created test client with ID: {client_id}")
        return client_id
    finally:
        db.close()

def test_no_current_employer():
    # Create a client
    client_id = setup_test_data()
    
    # Verify client exists in DB
    db = TestingSessionLocal()
    try:
        client_check = db.query(Client).filter(Client.id == client_id).first()
        print(f"Client exists: {client_check is not None}")
        
        # Verify no current employer exists
        ce = db.scalar(
            select(CurrentEmployer)
            .where(CurrentEmployer.client_id == client_id)
        )
        print(f"Current employer exists: {ce is not None}")
        
        # Call the API endpoint
        response = client.get(f"/api/v1/clients/{client_id}/current-employer")
        print(f"API Response status: {response.status_code}")
        print(f"API Response body: {response.json()}")
        
        # Validate response
        assert response.status_code == 404
        assert response.json()["detail"]["error"] == "אין מעסיק נוכחי רשום ללקוח"
        print("Test passed successfully!")
        
    finally:
        db.close()

if __name__ == "__main__":
    print("\n=== Testing Current Employer API ===")
    test_no_current_employer()
    print("\n=== Test completed ===")
