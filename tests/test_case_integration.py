"""
Integration tests for case detection API and workflow integration
"""
from datetime import date, timedelta
import json
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.client import Client
from app.models.current_employer import CurrentEmployer
from app.models.additional_income import AdditionalIncome, IncomeSourceType
from app.schemas.case import ClientCase

# Create a test client
client = TestClient(app)


@pytest.fixture
def test_client(test_db):
    """Create a test client with specific age"""
    # Create client with birth date exactly 45 years ago
    client = Client(
        first_name="Test",
        last_name="User",
        birth_date=date.today() - timedelta(days=45*365),
        id_number="123456789",
        is_active=True
    )
    test_db.add(client)
    test_db.commit()
    test_db.refresh(client)
    return client


@pytest.fixture
def retirement_age_client(test_db):
    """Create a client over retirement age"""
    client = Client(
        first_name="Retiree",
        last_name="User",
        birth_date=date.today() - timedelta(days=68*365),
        id_number="987654321",
        is_active=True
    )
    test_db.add(client)
    test_db.commit()
    test_db.refresh(client)
    return client


@pytest.fixture
def current_employer(test_db, test_client):
    """Create a current employer for the test client"""
    employer = CurrentEmployer(
        client_id=test_client.id,
        employer_name="Test Company",
        start_date=date.today() - timedelta(days=365),  # 1 year ago
        end_date=None,  # No end date
        monthly_salary=10000,
    )
    test_db.add(employer)
    test_db.commit()
    test_db.refresh(employer)
    return employer


@pytest.fixture
def business_income(test_db, test_client):
    """Create business income for the test client"""
    income = AdditionalIncome(
        client_id=test_client.id,
        source_type=IncomeSourceType.business,
        amount=15000,
        name="Business Income",
        start_date=date.today() - timedelta(days=365),  # 1 year ago
        end_date=None,  # No end date
    )
    test_db.add(income)
    test_db.commit()
    test_db.refresh(income)
    return income


def test_detect_case_retirement_age(test_db, retirement_age_client):
    """Test case detection for retirement age client"""
    response = client.get(f"/api/v1/clients/{retirement_age_client.id}/case/detect")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "result" in data
    assert data["result"]["case_id"] == ClientCase.PAST_RETIREMENT_AGE
    assert data["result"]["client_id"] == retirement_age_client.id
    assert "past_retirement_age" in data["result"]["reasons"]
    assert "detected_at" in data["result"]


def test_detect_case_no_employer(test_db, test_client):
    """Test case detection for client with no employer"""
    # Ensure no current employer
    test_db.query(CurrentEmployer).filter(
        CurrentEmployer.client_id == test_client.id
    ).delete()
    test_db.commit()
    
    # Ensure no business income
    test_db.query(AdditionalIncome).filter(
        AdditionalIncome.client_id == test_client.id
    ).delete()
    test_db.commit()
    
    response = client.get(f"/api/v1/clients/{test_client.id}/case/detect")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "result" in data
    assert data["result"]["case_id"] == ClientCase.NO_CURRENT_EMPLOYER
    assert data["result"]["client_id"] == test_client.id
    assert "no_current_employer" in data["result"]["reasons"]


def test_detect_case_self_employed(test_db, test_client, business_income):
    """Test case detection for self-employed client"""
    # Ensure no current employer
    test_db.query(CurrentEmployer).filter(
        CurrentEmployer.client_id == test_client.id
    ).delete()
    test_db.commit()
    
    response = client.get(f"/api/v1/clients/{test_client.id}/case/detect")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "result" in data
    assert data["result"]["case_id"] == ClientCase.SELF_EMPLOYED_ONLY
    assert data["result"]["client_id"] == test_client.id
    assert "has_business_income" in data["result"]["reasons"]


def test_detect_case_active_employer(test_db, test_client, current_employer):
    """Test case detection for active employer with no leave"""
    # Ensure no business income to avoid conflicts
    test_db.query(AdditionalIncome).filter(
        AdditionalIncome.client_id == test_client.id
    ).delete()
    test_db.commit()
    
    response = client.get(f"/api/v1/clients/{test_client.id}/case/detect")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "result" in data
    assert data["result"]["case_id"] == ClientCase.ACTIVE_NO_LEAVE
    assert data["result"]["client_id"] == test_client.id
    assert "has_current_employer" in data["result"]["reasons"]
    assert "no_planned_leave" in data["result"]["reasons"]


def test_detect_case_with_planned_leave(test_db, test_client, current_employer):
    """Test case detection for employer with planned leave"""
    # Set end date for current employer
    current_employer.end_date = date.today() + timedelta(days=180)  # 6 months from now
    test_db.add(current_employer)
    test_db.commit()
    
    response = client.get(f"/api/v1/clients/{test_client.id}/case/detect")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "result" in data
    assert data["result"]["case_id"] == ClientCase.REGULAR_WITH_LEAVE
    assert data["result"]["client_id"] == test_client.id
    assert "has_current_employer" in data["result"]["reasons"]
    assert "planned_leave_detected" in data["result"]["reasons"]


def test_detect_case_with_client_termination_date(test_db, test_client, current_employer):
    """Test case detection for client with planned termination date"""
    # No end date for employer but client has planned termination date
    current_employer.end_date = None
    test_db.add(current_employer)
    
    # Set planned termination date on client
    test_client.planned_termination_date = date.today() + timedelta(days=90)
    test_db.add(test_client)
    test_db.commit()
    
    response = client.get(f"/api/v1/clients/{test_client.id}/case/detect")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "result" in data
    assert data["result"]["case_id"] == ClientCase.REGULAR_WITH_LEAVE
    assert data["result"]["client_id"] == test_client.id
    assert "has_current_employer" in data["result"]["reasons"]
    assert "client_planned_termination" in data["result"]["reasons"]


def test_client_not_found(test_db):
    """Test case detection for non-existent client"""
    response = client.get("/api/v1/clients/9999/case/detect")
    
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert "not found" in data["detail"].lower()


def test_cashflow_with_case_integration(test_db, test_client, current_employer):
    """Test integration of case detection with cashflow API"""
    # Create a scenario for the client
    scenario_id = 1  # Assuming scenario exists or mock as needed
    
    # Call the cashflow API which should use case detection internally
    response = client.get(
        f"/api/v1/clients/{test_client.id}/cashflow/generate",
        params={
            "scenario_id": scenario_id,
            "from": "2025-01",
            "to": "2025-12",
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Check for case metadata in response
    assert len(data) > 0
    for row in data:
        if "meta" in row:
            assert "case_id" in row["meta"]
            # Based on our test setup, should be ACTIVE_NO_LEAVE (case 4)
            assert row["meta"]["case_id"] == ClientCase.ACTIVE_NO_LEAVE
            break


def test_scenario_compare_with_case_integration(test_db, test_client, current_employer):
    """Test integration of case detection with scenario compare API"""
    # Create scenarios for the client
    scenario_ids = [1, 2]  # Assuming scenarios exist or mock as needed
    
    # Call the compare API which should use case detection internally
    response = client.get(
        f"/api/v1/clients/{test_client.id}/scenarios/compare",
        params={
            "scenario_ids": ",".join(map(str, scenario_ids)),
            "from": "2025-01",
            "to": "2025-12",
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Check for case metadata in response
    assert "meta" in data
    assert "case" in data["meta"]
    assert data["meta"]["case"]["id"] == ClientCase.ACTIVE_NO_LEAVE
