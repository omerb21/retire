"""
Tests for PDF report generation functionality (Sprint 8).
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.database import get_db
from app.models import Client, Scenario
from app.services.report_service import generate_report_pdf
from app.schemas.report import ReportPdfRequest


client = TestClient(app)


def test_generate_pdf_ok(db_session: Session):
    """Test successful PDF generation returns valid PDF content."""
    # Create test client
    test_client = Client(
        id_number="123456789",
        full_name="Test Client",
        birth_date="1980-01-01"
    )
    db_session.add(test_client)
    db_session.flush()
    
    # Create test scenario
    test_scenario = Scenario(
        client_id=test_client.id,
        summary_results='{"total_pension": 1000000}',
        cashflow_projection='{"annual_cashflow": [{"net_cashflow": 50000}]}'
    )
    db_session.add(test_scenario)
    db_session.flush()
    
    # Test the service function
    request = ReportPdfRequest(
        from_="2025-01",
        to="2025-12",
        frequency="monthly"
    )
    
    pdf_bytes = generate_report_pdf(
        db=db_session,
        client_id=test_client.id,
        scenario_id=test_scenario.id,
        request=request
    )
    
    # Verify PDF content
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000  # PDF should have reasonable size
    assert pdf_bytes[:4] == b"%PDF"  # PDF magic number
    
    db_session.rollback()


def test_generate_pdf_api_ok(db_session: Session):
    """Test PDF generation API endpoint returns valid response."""
    # Create test client
    test_client = Client(
        id_number="123456789",
        full_name="Test Client API",
        birth_date="1980-01-01"
    )
    db_session.add(test_client)
    db_session.flush()
    
    # Create test scenario
    test_scenario = Scenario(
        client_id=test_client.id,
        summary_results='{"total_pension": 1000000}',
        cashflow_projection='{"annual_cashflow": [{"net_cashflow": 50000}]}'
    )
    db_session.add(test_scenario)
    db_session.flush()
    
    # Override get_db dependency
    def override_get_db():
        return db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    try:
        # Test API endpoint
        response = client.post(
            f"/api/v1/scenarios/{test_scenario.id}/report/pdf?client_id={test_client.id}",
            json={
                "from": "2025-01",
                "to": "2025-12",
                "frequency": "monthly",
                "sections": {
                    "summary": True,
                    "cashflow_table": True,
                    "net_chart": True,
                    "scenarios_compare": True
                }
            }
        )
        
        # Verify response
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert "attachment" in response.headers.get("content-disposition", "")
        
        # Verify PDF content
        pdf_content = response.content
        assert len(pdf_content) > 1000
        assert pdf_content[:4] == b"%PDF"
        
    finally:
        app.dependency_overrides.clear()
        db_session.rollback()


def test_generate_pdf_bad_range(db_session: Session):
    """Test PDF generation with invalid date range returns 400."""
    # Create test client
    test_client = Client(
        id_number="123456789",
        full_name="Test Client",
        birth_date="1980-01-01"
    )
    db_session.add(test_client)
    db_session.flush()
    
    # Create test scenario
    test_scenario = Scenario(
        client_id=test_client.id,
        summary_results='{"total_pension": 1000000}'
    )
    db_session.add(test_scenario)
    db_session.flush()
    
    # Override get_db dependency
    def override_get_db():
        return db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    try:
        # Test with invalid date range (from > to)
        response = client.post(
            f"/api/v1/scenarios/{test_scenario.id}/report/pdf?client_id={test_client.id}",
            json={
                "from": "2025-12",
                "to": "2025-01",  # Invalid: to < from
                "frequency": "monthly"
            }
        )
        
        # Should return validation error
        assert response.status_code == 422  # Pydantic validation error
        
    finally:
        app.dependency_overrides.clear()
        db_session.rollback()


def test_generate_pdf_bad_frequency(db_session: Session):
    """Test PDF generation with invalid frequency returns 422."""
    # Create test client
    test_client = Client(
        id_number="123456789",
        full_name="Test Client",
        birth_date="1980-01-01"
    )
    db_session.add(test_client)
    db_session.flush()
    
    # Create test scenario
    test_scenario = Scenario(
        client_id=test_client.id,
        summary_results='{"total_pension": 1000000}'
    )
    db_session.add(test_scenario)
    db_session.flush()
    
    # Override get_db dependency
    def override_get_db():
        return db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    try:
        # Test with invalid frequency
        response = client.post(
            f"/api/v1/scenarios/{test_scenario.id}/report/pdf?client_id={test_client.id}",
            json={
                "from": "2025-01",
                "to": "2025-12",
                "frequency": "weekly"  # Invalid: only "monthly" supported
            }
        )
        
        # Should return validation error
        assert response.status_code == 422  # Pydantic validation error
        
    finally:
        app.dependency_overrides.clear()
        db_session.rollback()


def test_generate_pdf_client_not_found(db_session: Session):
    """Test PDF generation with non-existent client returns 400."""
    # Override get_db dependency
    def override_get_db():
        return db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    try:
        # Test with non-existent client
        response = client.post(
            "/api/v1/scenarios/999/report/pdf?client_id=99999",
            json={
                "from": "2025-01",
                "to": "2025-12",
                "frequency": "monthly"
            }
        )
        
        # Should return client not found error
        assert response.status_code == 400
        assert "not found" in response.json()["detail"].lower()
        
    finally:
        app.dependency_overrides.clear()
        db_session.rollback()


def test_generate_pdf_invalid_date_format(db_session: Session):
    """Test PDF generation with invalid date format returns 422."""
    # Create test client
    test_client = Client(
        id_number="123456789",
        full_name="Test Client",
        birth_date="1980-01-01"
    )
    db_session.add(test_client)
    db_session.flush()
    
    # Create test scenario
    test_scenario = Scenario(
        client_id=test_client.id,
        summary_results='{"total_pension": 1000000}'
    )
    db_session.add(test_scenario)
    db_session.flush()
    
    # Override get_db dependency
    def override_get_db():
        return db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    try:
        # Test with invalid date format
        response = client.post(
            f"/api/v1/scenarios/{test_scenario.id}/report/pdf?client_id={test_client.id}",
            json={
                "from": "2025/01",  # Invalid format: should be YYYY-MM
                "to": "2025-12",
                "frequency": "monthly"
            }
        )
        
        # Should return validation error
        assert response.status_code == 422
        
    finally:
        app.dependency_overrides.clear()
        db_session.rollback()
