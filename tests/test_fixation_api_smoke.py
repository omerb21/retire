"""
Smoke test for fixation API endpoints
"""
import pytest
from fastapi.testclient import TestClient
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import get_db, Base
from app.main import app as fastapi_app
from app.models import Client, FixationResult

test_engine = create_engine("sqlite:///test_suite.db", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
Base.metadata.create_all(bind=test_engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

fastapi_app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    """Set up test database"""
    # Create a test client
    db = TestingSessionLocal()
    test_client = Client(
        id_number_raw="123456782",
        id_number="123456782",
        full_name="Test Client",
        birth_date=date(1980, 1, 1),
        is_active=True
    )
    db.add(test_client)
    db.commit()
    db.close()
    
    yield
    
    # Clean up
    test_engine.dispose()
    import os
    if os.path.exists("test_suite.db"):
        os.remove("test_suite.db")


def test_compute_fixation_returns_200():
    """Test that POST /api/v1/fixation/{client_id}/compute returns 200"""
    client = TestClient(fastapi_app)
    
    response = client.post("/api/v1/fixation/1/compute")
    
    assert response.status_code == 200
    data = response.json()
    
    # Check required keys exist
    assert "client_id" in data
    assert "persisted_id" in data
    assert "outputs" in data
    assert "engine_version" in data
    
    # Check client_id matches
    assert data["client_id"] == 1
    
    # Check outputs structure
    outputs = data["outputs"]
    assert "exempt_capital_remaining" in outputs
    assert "used_commutation" in outputs
    assert "annex_161d_ready" in outputs
    
    # Check engine version
    assert data["engine_version"] == "fixation-sprint2-1"
    
    # Check that persisted_id is a positive integer
    assert isinstance(data["persisted_id"], int)
    assert data["persisted_id"] > 0


def test_compute_fixation_with_payload():
    """Test compute fixation with optional payload"""
    client = TestClient(fastapi_app)
    
    payload = {
        "scenario_id": 2,
        "params": {"test_param": "test_value"}
    }
    
    response = client.post("/api/v1/fixation/1/compute", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    
    # Check all required fields are present
    assert "client_id" in data
    assert "persisted_id" in data
    assert "outputs" in data
    assert "engine_version" in data


def test_compute_fixation_creates_database_record():
    """Test that compute fixation creates a record in the database"""
    client = TestClient(fastapi_app)
    
    # Get initial count
    db = TestingSessionLocal()
    initial_count = db.query(FixationResult).count()
    db.close()
    
    # Make API call
    response = client.post("/api/v1/fixation/1/compute")
    assert response.status_code == 200
    
    # Check that a new record was created
    db = TestingSessionLocal()
    final_count = db.query(FixationResult).count()
    db.close()
    
    assert final_count == initial_count + 1


def test_compute_fixation_nonexistent_client_returns_404():
    """Test that compute fixation with nonexistent client returns 404"""
    client = TestClient(fastapi_app)
    
    response = client.post("/api/v1/fixation/999/compute")
    
    assert response.status_code == 404
