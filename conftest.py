"""
Global pytest configuration and fixtures
"""
import pytest
import tempfile
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from app.main import app
from db.session import get_db
from models.base import Base

# Test database configuration
@pytest.fixture(scope="session")
def test_db():
    """Create test database for the session"""
    # Use in-memory SQLite for tests
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    yield TestingSessionLocal, engine
    
    # Cleanup
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def db_session(test_db):
    """Create database session for individual tests"""
    TestingSessionLocal, engine = test_db
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def client(test_db):
    """FastAPI test client with test database"""
    TestingSessionLocal, engine = test_db
    
    def override_get_db():
        try:
            db = TestingSessionLocal()
            yield db
        finally:
            db.close()
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    # Clean up overrides
    app.dependency_overrides.clear()

@pytest.fixture
def temp_file():
    """Create temporary file for tests"""
    fd, path = tempfile.mkstemp()
    try:
        yield path
    finally:
        os.close(fd)
        if os.path.exists(path):
            os.remove(path)

@pytest.fixture
def sample_xml_content():
    """Sample XML content for import tests"""
    return """<?xml version="1.0" encoding="UTF-8"?>
    <products>
        <product>
            <fund_id>12345</fund_id>
            <fund_name>Test Pension Fund</fund_name>
            <management_company>Test Management Co.</management_company>
            <total_balance>1000000</total_balance>
            <annual_return>0.05</annual_return>
            <management_fee>0.015</management_fee>
        </product>
        <product>
            <fund_id>67890</fund_id>
            <fund_name>Another Fund</fund_name>
            <management_company>Another Management</management_company>
            <total_balance>500000</total_balance>
            <annual_return>0.04</annual_return>
            <management_fee>0.02</management_fee>
        </product>
    </products>"""

@pytest.fixture
def sample_client_data():
    """Sample client data for tests"""
    return {
        "client_id": "123456789",
        "full_name": "John Doe",
        "birth_date": "1970-01-01",
        "gender": "M",
        "email": "john.doe@example.com",
        "phone": "050-1234567",
        "address": "123 Main St, Tel Aviv"
    }

@pytest.fixture
def sample_scenario_data():
    """Sample scenario data for tests"""
    return {
        "name": "Test Retirement Scenario",
        "parameters": {
            "retirement_age": 67,
            "life_expectancy": 85,
            "indexation_rate": 0.02,
            "initial_capital": 1000000,
            "grants": [
                {
                    "type": "severance",
                    "amount": 200000,
                    "payment_year": 2024
                }
            ]
        }
    }

@pytest.fixture
def sample_cashflow_data():
    """Sample cashflow data for tests"""
    return [
        {
            "year": 2024,
            "gross_income": 100000,
            "pension_income": 60000,
            "grant_income": 40000,
            "other_income": 0,
            "tax": 20000,
            "net_income": 80000
        },
        {
            "year": 2025,
            "gross_income": 105000,
            "pension_income": 62000,
            "grant_income": 43000,
            "other_income": 0,
            "tax": 21000,
            "net_income": 84000
        },
        {
            "year": 2026,
            "gross_income": 110000,
            "pension_income": 64000,
            "grant_income": 46000,
            "other_income": 0,
            "tax": 22000,
            "net_income": 88000
        }
    ]

# Pytest markers configuration
def pytest_configure(config):
    """Configure pytest markers"""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "e2e: End-to-end tests")
    config.addinivalue_line("markers", "slow: Slow running tests")
    config.addinivalue_line("markers", "pdf: PDF generation tests")

def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers automatically"""
    for item in items:
        # Add markers based on test file location
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)
        
        # Add slow marker for PDF tests
        if "pdf" in str(item.fspath) or "pdf" in item.name:
            item.add_marker(pytest.mark.pdf)
            item.add_marker(pytest.mark.slow)
