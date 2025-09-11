"""
Integration tests for PDF report generation
"""
import pytest
import tempfile
import os
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from db.session import get_db
from models.base import Base
from models.client import Client
from models.scenario import Scenario
from models.scenario_cashflow import ScenarioCashflow
from services.scenario_engine import run_scenario

# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_reports.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="module")
def setup_database():
    """Set up test database"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def client():
    """FastAPI test client"""
    return TestClient(app)

@pytest.fixture
def db_session():
    """Database session for tests"""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def sample_client(db_session):
    """Create sample client for testing"""
    client = Client(
        client_id="123456789",
        full_name="Test Client",
        birth_date="1970-01-01",
        gender="M",
        email="test@example.com"
    )
    db_session.add(client)
    db_session.commit()
    db_session.refresh(client)
    return client

@pytest.fixture
def sample_scenario_with_cashflow(db_session, sample_client):
    """Create sample scenario with cashflow data"""
    scenario = Scenario(
        client_id=sample_client.id,
        name="Test Scenario",
        parameters={
            "retirement_age": 67,
            "life_expectancy": 85,
            "indexation_rate": 0.02,
            "pension_calculation": {
                "total_capital": 1000000,
                "effective_capital": 950000,
                "annual_pension": 52777
            },
            "processed_grants": [
                {
                    "grant_type": "Severance",
                    "original_amount": 200000,
                    "payment_year": 2024
                }
            ]
        },
        status="completed"
    )
    db_session.add(scenario)
    db_session.commit()
    db_session.refresh(scenario)
    
    # Add cashflow data
    cashflow_data = [
        ScenarioCashflow(
            scenario_id=scenario.id,
            year=2024,
            gross_income=100000,
            pension_income=60000,
            grant_income=40000,
            tax=20000,
            net_income=80000
        ),
        ScenarioCashflow(
            scenario_id=scenario.id,
            year=2025,
            gross_income=105000,
            pension_income=62000,
            grant_income=43000,
            tax=21000,
            net_income=84000
        )
    ]
    
    for cashflow in cashflow_data:
        db_session.add(cashflow)
    
    db_session.commit()
    return scenario

class TestPDFReportGeneration:
    """Test PDF report generation endpoints"""
    
    def test_generate_scenario_pdf_success(self, client, sample_scenario_with_cashflow, setup_database):
        """Test successful PDF generation for scenario"""
        scenario_id = sample_scenario_with_cashflow.id
        
        response = client.post(f"/api/v1/reports/scenario/{scenario_id}/pdf")
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert "attachment" in response.headers["content-disposition"]
        assert len(response.content) > 1000  # PDF should have reasonable size
        
        # Verify PDF header
        assert response.content[:4] == b'%PDF'
    
    def test_generate_scenario_pdf_not_found(self, client, setup_database):
        """Test PDF generation for non-existent scenario"""
        response = client.post("/api/v1/reports/scenario/999/pdf")
        
        assert response.status_code == 404
        assert "Scenario not found" in response.json()["detail"]
    
    def test_generate_comprehensive_report_success(self, client, sample_scenario_with_cashflow, setup_database):
        """Test comprehensive client report generation"""
        client_id = sample_scenario_with_cashflow.client_id
        
        response = client.post(f"/api/v1/reports/client/{client_id}/comprehensive-report")
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert len(response.content) > 1000
        assert response.content[:4] == b'%PDF'
    
    def test_generate_comprehensive_report_no_scenarios(self, client, sample_client, setup_database):
        """Test comprehensive report with no completed scenarios"""
        response = client.post(f"/api/v1/reports/client/{sample_client.id}/comprehensive-report")
        
        assert response.status_code == 400
        assert "No completed scenarios found" in response.json()["detail"]
    
    def test_preview_scenario_report_data(self, client, sample_scenario_with_cashflow, setup_database):
        """Test scenario report data preview"""
        scenario_id = sample_scenario_with_cashflow.id
        
        response = client.get(f"/api/v1/reports/scenario/{scenario_id}/preview")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "context" in data
        assert "cashflow_summary" in data
        assert "sample_cashflow" in data
        
        # Verify context data
        context = data["context"]
        assert context["client_name"] == "Test Client"
        assert context["scenario_name"] == "Test Scenario"
        assert context["retirement_age"] == 67
        
        # Verify cashflow summary
        summary = data["cashflow_summary"]
        assert summary["years_count"] == 2
        assert summary["total_gross_income"] == 205000
        assert summary["total_net_income"] == 164000
        assert summary["first_year"] == 2024
        assert summary["last_year"] == 2025

class TestPDFReportEdgeCases:
    """Test edge cases and error conditions"""
    
    def test_scenario_without_cashflow(self, client, db_session, sample_client, setup_database):
        """Test PDF generation for scenario without cashflow data"""
        scenario = Scenario(
            client_id=sample_client.id,
            name="Empty Scenario",
            parameters={},
            status="pending"
        )
        db_session.add(scenario)
        db_session.commit()
        db_session.refresh(scenario)
        
        response = client.post(f"/api/v1/reports/scenario/{scenario.id}/pdf")
        
        assert response.status_code == 400
        assert "No cashflow data available" in response.json()["detail"]
    
    def test_client_not_found(self, client, setup_database):
        """Test PDF generation for non-existent client"""
        response = client.post("/api/v1/reports/client/999/comprehensive-report")
        
        assert response.status_code == 404
        assert "Client not found" in response.json()["detail"]
    
    def test_preview_scenario_not_found(self, client, setup_database):
        """Test preview for non-existent scenario"""
        response = client.get("/api/v1/reports/scenario/999/preview")
        
        assert response.status_code == 404
        assert "Scenario not found" in response.json()["detail"]

class TestPDFContentValidation:
    """Test PDF content and structure validation"""
    
    def test_pdf_content_structure(self, client, sample_scenario_with_cashflow, setup_database):
        """Test that generated PDF has expected structure"""
        scenario_id = sample_scenario_with_cashflow.id
        
        response = client.post(f"/api/v1/reports/scenario/{scenario_id}/pdf")
        
        assert response.status_code == 200
        pdf_content = response.content
        
        # Basic PDF structure validation
        assert pdf_content.startswith(b'%PDF-')
        assert b'%%EOF' in pdf_content
        assert len(pdf_content) > 5000  # Reasonable size for a comprehensive report
        
        # Check for PDF objects (basic structure)
        assert b'/Type' in pdf_content
        assert b'/Page' in pdf_content
    
    def test_hebrew_text_encoding(self, client, sample_scenario_with_cashflow, setup_database):
        """Test Hebrew text handling in PDF"""
        scenario_id = sample_scenario_with_cashflow.id
        
        response = client.post(f"/api/v1/reports/scenario/{scenario_id}/pdf")
        
        assert response.status_code == 200
        # PDF should be generated without encoding errors
        assert len(response.content) > 1000

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
