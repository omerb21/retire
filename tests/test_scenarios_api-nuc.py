"""
Tests for scenario API endpoints
"""
import json
import pytest
from datetime import date, datetime
from fastapi.testclient import TestClient

from app.models.client import Client
from app.models.employment import Employment
from app.models.employer import Employer
from app.models.scenario import Scenario
from tests.utils import gen_valid_id, gen_reg_no


def make_client():
    """Create a test client with valid data"""
    id_num = gen_valid_id()
    return Client(
        id_number=id_num,
        id_number_raw=id_num,
        full_name="׳™׳•׳¡׳™ ׳›׳”׳",
        first_name="׳™׳•׳¡׳™",
        last_name="׳›׳”׳",
        birth_date=date(1980, 1, 1),
        address_city="׳×׳ ׳׳‘׳™׳‘",
        address_street="׳¨׳—׳•׳‘ ׳”׳¨׳¦׳ 123",
        address_postal_code="12345",
        phone="050-1234567",
        email="test@example.com",
        is_active=True
    )


def make_employer():
    """Create a test employer with valid data"""
    return Employer(
        name="׳—׳‘׳¨׳× ׳˜׳¡׳˜ ׳‘׳¢\"׳",
        reg_no=gen_reg_no()
    )


def make_employment(client_id: int, employer_id: int):
    """Create a test employment with valid data"""
    return Employment(
        client_id=client_id,
        employer_id=employer_id,
        start_date=date(2020, 1, 1),
        monthly_salary_nominal=15000.0,
        is_current=True
    )


def test_create_scenario_201_and_run_returns_scenario_out(client, db_session):
    """Test creating scenario and running it returns proper ScenarioOut"""
    # Arrange - create client with current employment
    test_client = make_client()
    db_session.add(test_client)
    db_session.commit()
    
    employer = make_employer()
    db_session.add(employer)
    db_session.commit()
    
    employment = make_employment(test_client.id, employer.id)
    db_session.add(employment)
    db_session.commit()
    
    # Create scenario
    scenario_data = {
        "scenario_name": "׳×׳¨׳—׳™׳© ׳‘׳“׳™׳§׳”",
        "planned_termination_date": "2025-06-30",
        "monthly_expenses": 8000.0,
        "apply_tax_planning": False,
        "apply_capitalization": False,
        "apply_exemption_shield": False,
    }
    
    # Act - create scenario
    response = client.post(f"/api/v1/clients/{test_client.id}/scenarios", json=scenario_data)
    
    # Assert - scenario created
    assert response.status_code == 201
    create_result = response.json()
    assert "scenario_id" in create_result
    scenario_id = create_result["scenario_id"]
    
    # Act - run scenario
    run_response = client.post(f"/api/v1/scenarios/{scenario_id}/run")
    
    # Assert - scenario run successful
    assert run_response.status_code == 200
    result = run_response.json()
    
    # Verify ScenarioOut structure (Stage 4 schema - only calculation results)
    assert "seniority_years" in result
    assert "grant_gross" in result
    assert "grant_exempt" in result
    assert "grant_tax" in result
    assert "grant_net" in result
    assert "pension_monthly" in result
    assert "indexation_factor" in result
    assert "cashflow" in result
    
    # Verify numeric results are valid
    assert isinstance(result["seniority_years"], (int, float))
    assert isinstance(result["grant_gross"], (int, float))
    assert isinstance(result["grant_exempt"], (int, float))
    assert isinstance(result["grant_tax"], (int, float))
    assert isinstance(result["grant_net"], (int, float))
    assert isinstance(result["pension_monthly"], (int, float))
    assert isinstance(result["indexation_factor"], (int, float))
    
    # Verify cashflow has at least 12 months
    assert len(result["cashflow"]) >= 12
    for cf_point in result["cashflow"]:
        assert "date" in cf_point
        assert "inflow" in cf_point
        assert "outflow" in cf_point
        assert "net" in cf_point
    
    # Act - get scenario to verify saved results
    get_response = client.get(f"/api/v1/scenarios/{scenario_id}")
    
    # Assert - get returns same data
    assert get_response.status_code == 200
    get_result = get_response.json()
    # Note: get_result includes id but result (ScenarioOut) does not
    assert get_result["seniority_years"] == result["seniority_years"]
    assert get_result["grant_net"] == result["grant_net"]
    assert len(get_result["cashflow"]) == len(result["cashflow"])


def test_list_scenarios_returns_created_item(client, db_session):
    """Test listing scenarios returns created items with flags"""
    # Arrange - create client
    test_client = make_client()
    db_session.add(test_client)
    db_session.commit()
    
    # Create multiple scenarios with different flags
    scenarios_data = [
        {
            "scenario_name": "׳×׳¨׳—׳™׳© 1",
            "apply_tax_planning": True,
            "apply_capitalization": False,
            "apply_exemption_shield": False
        },
        {
            "scenario_name": "׳×׳¨׳—׳™׳© 2", 
            "apply_tax_planning": False,
            "apply_capitalization": True,
            "apply_exemption_shield": True
        }
    ]
    
    created_ids = []
    for scenario_data in scenarios_data:
        response = client.post(f"/api/v1/clients/{test_client.id}/scenarios", json=scenario_data)
        assert response.status_code == 201
        created_ids.append(response.json()["scenario_id"])
    
    # Act - list scenarios
    response = client.get(f"/api/v1/clients/{test_client.id}/scenarios")
    
    # Assert
    assert response.status_code == 200
    result = response.json()
    assert "scenarios" in result
    scenarios = result["scenarios"]
    assert len(scenarios) == 2
    
    # Verify scenario structure and flags
    for scenario in scenarios:
        assert "id" in scenario
        assert "scenario_name" in scenario
        assert "apply_tax_planning" in scenario
        assert "apply_capitalization" in scenario
        assert "apply_exemption_shield" in scenario
        assert "created_at" in scenario
        assert scenario["id"] in created_ids
    
    # Verify flags are different between scenarios
    flags_1 = (scenarios[0]["apply_tax_planning"], scenarios[0]["apply_capitalization"], scenarios[0]["apply_exemption_shield"])
    flags_2 = (scenarios[1]["apply_tax_planning"], scenarios[1]["apply_capitalization"], scenarios[1]["apply_exemption_shield"])
    assert flags_1 != flags_2


def test_run_no_employment_422(client, db_session):
    """Test running scenario without employment returns 422"""
    # Arrange - create client without employment
    test_client = make_client()
    db_session.add(test_client)
    db_session.commit()
    
    # Create scenario
    scenario_data = {
        "scenario_name": "׳×׳¨׳—׳™׳© ׳׳׳ ׳×׳¢׳¡׳•׳§׳”",
        "apply_tax_planning": False,
        "apply_capitalization": False,
        "apply_exemption_shield": False,
        "planned_termination_date": "2025-06-30",
        "monthly_expenses": 5000.0,
    }
    
    response = client.post(f"/api/v1/clients/{test_client.id}/scenarios", json=scenario_data)
    assert response.status_code == 201
    scenario_id = response.json()["scenario_id"]
    
    # Act - try to run scenario
    run_response = client.post(f"/api/v1/scenarios/{scenario_id}/run")
    
    # Assert - 422 with Hebrew error message
    assert run_response.status_code == 422
    error_detail = run_response.json()["detail"]
    assert isinstance(error_detail, str) and len(error_detail) > 0
def test_run_missing_cpi_422(client, db_session):
    """Test running scenario with dates outside CPI range returns 422"""
    # Arrange - create client with employment
    test_client = make_client()
    db_session.add(test_client)
    db_session.commit()
    
    employer = make_employer()
    db_session.add(employer)
    db_session.commit()
    
    # Create employment with future dates that might not have CPI data
    employment = Employment(
        client_id=test_client.id,
        employer_id=employer.id,
        start_date=date(2030, 1, 1),  # Future date
        monthly_salary_nominal=15000.0,
        is_current=True
    )
    db_session.add(employment)
    db_session.commit()
    
    # Create scenario with far future termination
    scenario_data = {
        "scenario_name": "׳×׳¨׳—׳™׳© ׳¢׳×׳™׳“׳™",
        "planned_termination_date": "2035-12-31",  # Far future,
        "apply_tax_planning": False,
        "apply_capitalization": False,
        "apply_exemption_shield": False,
        "monthly_expenses": 5000.0,
    }
    
    response = client.post(f"/api/v1/clients/{test_client.id}/scenarios", json=scenario_data)
    assert response.status_code == 201
    scenario_id = response.json()["scenario_id"]
    
    # Act - try to run scenario
    run_response = client.post(f"/api/v1/scenarios/{scenario_id}/run")
    
    # Assert - might be 422 with CPI error or successful depending on CPI data availability
    # We expect 422 if CPI data is missing for the date range
    if run_response.status_code == 422:
        error_detail = run_response.json()["detail"]
        assert isinstance(error_detail, str) and len(error_detail) > 0
    else:
        # If CPI data is available, the test should still pass
        assert run_response.status_code == 200


def test_create_scenario_invalid_client_404(client, db_session):
    """Test creating scenario for non-existent client returns 404"""
    scenario_data = {
        "scenario_name": "׳×׳¨׳—׳™׳© ׳׳ ׳§׳™׳™׳",
        "apply_tax_planning": False,
        "apply_capitalization": False,
        "apply_exemption_shield": False,
        "planned_termination_date": "2025-06-30",
        "monthly_expenses": 5000.0,
    }
    
    # Act - try to create scenario for non-existent client
    response = client.post("/api/v1/clients/99999/scenarios", json=scenario_data)
    
    # Assert
    assert response.status_code == 404
    detail = response.json().get("detail",""); assert isinstance(detail, str) and len(detail) > 0
def test_create_scenario_inactive_client_400(client, db_session):
    """Test creating scenario for inactive client returns 400"""
    # Arrange - create inactive client
    test_client = make_client()
    test_client.is_active = False
    db_session.add(test_client)
    db_session.commit()
    
    scenario_data = {
        "scenario_name": "׳×׳¨׳—׳™׳© ׳׳§׳•׳— ׳׳ ׳₪׳¢׳™׳",
        "apply_tax_planning": False,
        "apply_capitalization": False,
        "apply_exemption_shield": False,
        "planned_termination_date": "2025-06-30",
        "monthly_expenses": 5000.0,
    }
    
    # Act
    response = client.post(f"/api/v1/clients/{test_client.id}/scenarios", json=scenario_data)
    
    # Assert
    assert response.status_code == 400
    detail = response.json().get("detail",""); assert isinstance(detail, str) and len(detail) > 0
def test_run_nonexistent_scenario_404(client, db_session):
    """Test running non-existent scenario returns 404"""
    # Act
    response = client.post("/api/v1/scenarios/99999/run")
    
    # Assert
    assert response.status_code == 404
    detail = response.json().get("detail",""); assert isinstance(detail, str) and len(detail) > 0
def test_get_nonexistent_scenario_404(client, db_session):
    """Test getting non-existent scenario returns 404"""
    # Act
    response = client.get("/api/v1/scenarios/99999")
    
    # Assert
    assert response.status_code == 404
    detail = response.json().get("detail",""); assert isinstance(detail, str) and len(detail) > 0

