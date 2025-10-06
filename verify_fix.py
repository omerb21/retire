"""
Direct minimal verification script for the current employer fix
"""
import sys
import os
from datetime import date
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from app.database import Base
from app.main import app
from app.models.client import Client

# Print directly to stdout to ensure visibility
def print_flush(*args, **kwargs):
    print(*args, **kwargs)
    sys.stdout.flush()

print_flush("===== STARTING VERIFICATION SCRIPT =====")

# Create in-memory test db
print_flush("Creating test database")
engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autoflush=True, expire_on_commit=False, bind=engine)
Base.metadata.create_all(bind=engine)

# Override the dependency
def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides["get_db"] = override_get_db

# Create test client
print_flush("Creating FastAPI test client")
client = TestClient(app)

# Create a db session
print_flush("Creating database session")
db = TestingSessionLocal()

# Create a test client
print_flush("Creating test client in database")
test_client = Client(
    id_number_raw="verification123",
    id_number="verification123",
    full_name="Verification Client",
    birth_date=date(1990, 1, 1),
    is_active=True
)
db.add(test_client)
db.commit()
db.refresh(test_client)
client_id = test_client.id
print_flush(f"Created client with ID: {client_id}")

# Verify client is in database
print_flush("Verifying client exists in database")
check_client = db.query(Client).filter(Client.id == client_id).first()
if check_client:
    print_flush(f"Client verified in DB: ID={check_client.id}, Name={check_client.full_name}")
else:
    print_flush("WARNING: Client not found in verification query!")

# Call the API endpoint
print_flush("Calling the API endpoint")
endpoint = f"/api/v1/clients/{client_id}/current-employer"
print_flush(f"GET {endpoint}")
response = client.get(endpoint)
print_flush(f"Response status: {response.status_code}")
print_flush(f"Response body: {response.text}")

# Verify the result
print_flush("Verifying response")
if response.status_code == 404:
    error_msg = response.json()["detail"]["error"]
    expected = "אין מעסיק נוכחי רשום ללקוח"
    if error_msg == expected:
        print_flush("✅ SUCCESS: Got correct error message")
        print_flush(f"Actual: '{error_msg}'")
        print_flush(f"Expected: '{expected}'")
    else:
        print_flush("❌ FAILURE: Got wrong error message")
        print_flush(f"Actual: '{error_msg}'")
        print_flush(f"Expected: '{expected}'")
else:
    print_flush("❌ FAILURE: Expected status code 404, got {response.status_code}")

print_flush("===== VERIFICATION COMPLETE =====")
