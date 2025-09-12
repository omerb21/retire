"""
End-to-end tests for complete retirement planning workflow
"""
import pytest
import tempfile
import os
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from db.session import get_db
from app.database import Base
import json

# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_e2e.db"
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

class TestCompleteWorkflow:
    """Test complete retirement planning workflow"""
    
    def test_full_retirement_planning_workflow(self, client, setup_database):
        """Test complete workflow from client creation to PDF report"""
        
        # Step 1: Create client
        client_data = {
            "client_id": "123456789",
            "full_name": "John Doe",
            "birth_date": "1970-01-01",
            "gender": "M",
            "email": "john.doe@example.com",
            "phone": "050-1234567"
        }
        
        response = client.post("/api/v1/clients", json=client_data)
        assert response.status_code == 201
        created_client = response.json()
        client_id = created_client["id"]
        
        # Step 2: Create scenario
        scenario_data = {
            "name": "Primary Retirement Scenario",
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
        
        response = client.post(f"/api/v1/scenarios", json={**scenario_data, "client_id": client_id})
        assert response.status_code == 201
        created_scenario = response.json()
        scenario_id = created_scenario["id"]
        
        # Step 3: Run scenario calculation
        response = client.post(f"/api/v1/scenarios/{scenario_id}/run")
        assert response.status_code == 200
        
        # Step 4: Get cashflow data
        response = client.get(f"/api/v1/scenarios/{scenario_id}/cashflow")
        assert response.status_code == 200
        cashflow_data = response.json()
        assert len(cashflow_data) > 0
        
        # Step 5: Generate PDF report
        response = client.post(f"/api/v1/reports/scenario/{scenario_id}/pdf")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert len(response.content) > 1000
        
        # Step 6: Preview report data
        response = client.get(f"/api/v1/reports/scenario/{scenario_id}/preview")
        assert response.status_code == 200
        preview_data = response.json()
        assert preview_data["context"]["client_name"] == "John Doe"
        assert preview_data["cashflow_summary"]["years_count"] > 0
    
    def test_xml_import_workflow(self, client, setup_database):
        """Test XML import and product mapping workflow"""
        
        # Create sample XML content
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <products>
            <product>
                <fund_id>12345</fund_id>
                <fund_name>Test Pension Fund</fund_name>
                <management_company>Test Management</management_company>
                <total_balance>500000</total_balance>
                <annual_return>0.05</annual_return>
            </product>
        </products>"""
        
        # Create temporary XML file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-8') as tmp_file:
            tmp_file.write(xml_content)
            xml_file_path = tmp_file.name
        
        try:
            # Step 1: Import XML
            with open(xml_file_path, 'rb') as f:
                files = {"file": ("test.xml", f, "application/xml")}
                response = client.post("/api/v1/imports/xml", files=files)
            
            assert response.status_code == 200
            import_result = response.json()
            assert import_result["status"] == "success"
            
            # Step 2: List imported products
            response = client.get("/api/v1/imports/saving-products")
            assert response.status_code == 200
            products = response.json()
            assert len(products["items"]) > 0
            
            # Step 3: List existing products (mapped)
            response = client.get("/api/v1/imports/existing-products")
            assert response.status_code == 200
            
            # Step 4: List new products (unmapped)
            response = client.get("/api/v1/imports/new-products")
            assert response.status_code == 200
            
        finally:
            # Clean up
            if os.path.exists(xml_file_path):
                os.remove(xml_file_path)
    
    def test_calculation_logging_workflow(self, client, setup_database):
        """Test calculation logging throughout workflow"""
        
        # Create client and scenario
        client_data = {
            "client_id": "987654321",
            "full_name": "Jane Smith",
            "birth_date": "1975-05-15",
            "gender": "F",
            "email": "jane.smith@example.com"
        }
        
        response = client.post("/api/v1/clients", json=client_data)
        assert response.status_code == 201
        client_id = response.json()["id"]
        
        scenario_data = {
            "client_id": client_id,
            "name": "Logging Test Scenario",
            "parameters": {
                "retirement_age": 65,
                "life_expectancy": 80,
                "initial_capital": 800000
            }
        }
        
        response = client.post("/api/v1/scenarios", json=scenario_data)
        assert response.status_code == 201
        scenario_id = response.json()["id"]
        
        # Run scenario (this should trigger calculation logging)
        response = client.post(f"/api/v1/scenarios/{scenario_id}/run")
        assert response.status_code == 200
        
        # Verify calculation logs were created
        # Note: This would require an endpoint to retrieve calculation logs
        # For now, we just verify the scenario ran successfully
        response = client.get(f"/api/v1/scenarios/{scenario_id}")
        assert response.status_code == 200
        scenario = response.json()
        assert scenario["status"] == "completed"

class TestErrorHandling:
    """Test error handling in complete workflows"""
    
    def test_invalid_client_data(self, client, setup_database):
        """Test handling of invalid client data"""
        
        invalid_client_data = {
            "client_id": "",  # Invalid empty client_id
            "full_name": "",  # Invalid empty name
            "birth_date": "invalid-date",  # Invalid date format
            "gender": "X",  # Invalid gender
            "email": "invalid-email"  # Invalid email format
        }
        
        response = client.post("/api/v1/clients", json=invalid_client_data)
        assert response.status_code == 422  # Validation error
    
    def test_scenario_without_client(self, client, setup_database):
        """Test scenario creation with non-existent client"""
        
        scenario_data = {
            "client_id": 999,  # Non-existent client
            "name": "Invalid Scenario",
            "parameters": {}
        }
        
        response = client.post("/api/v1/scenarios", json=scenario_data)
        assert response.status_code in [400, 404]  # Client not found
    
    def test_pdf_generation_without_cashflow(self, client, setup_database):
        """Test PDF generation for scenario without cashflow"""
        
        # Create client and scenario but don't run it
        client_data = {
            "client_id": "111222333",
            "full_name": "Test User",
            "birth_date": "1980-01-01",
            "gender": "M",
            "email": "test@example.com"
        }
        
        response = client.post("/api/v1/clients", json=client_data)
        assert response.status_code == 201
        client_id = response.json()["id"]
        
        scenario_data = {
            "client_id": client_id,
            "name": "Empty Scenario",
            "parameters": {}
        }
        
        response = client.post("/api/v1/scenarios", json=scenario_data)
        assert response.status_code == 201
        scenario_id = response.json()["id"]
        
        # Try to generate PDF without running scenario
        response = client.post(f"/api/v1/reports/scenario/{scenario_id}/pdf")
        assert response.status_code == 400
        assert "No cashflow data available" in response.json()["detail"]

class TestPerformance:
    """Test performance aspects of the system"""
    
    def test_large_cashflow_pdf_generation(self, client, setup_database):
        """Test PDF generation with large cashflow dataset"""
        
        # Create client
        client_data = {
            "client_id": "555666777",
            "full_name": "Performance Test",
            "birth_date": "1960-01-01",
            "gender": "M",
            "email": "perf@example.com"
        }
        
        response = client.post("/api/v1/clients", json=client_data)
        assert response.status_code == 201
        client_id = response.json()["id"]
        
        # Create scenario with long retirement period
        scenario_data = {
            "client_id": client_id,
            "name": "Long Retirement Scenario",
            "parameters": {
                "retirement_age": 60,
                "life_expectancy": 95,  # 35 years of retirement
                "initial_capital": 2000000
            }
        }
        
        response = client.post("/api/v1/scenarios", json=scenario_data)
        assert response.status_code == 201
        scenario_id = response.json()["id"]
        
        # Run scenario
        response = client.post(f"/api/v1/scenarios/{scenario_id}/run")
        assert response.status_code == 200
        
        # Generate PDF (should handle large dataset)
        response = client.post(f"/api/v1/reports/scenario/{scenario_id}/pdf")
        assert response.status_code == 200
        assert len(response.content) > 1000
    
    def test_multiple_scenarios_comparison(self, client, setup_database):
        """Test handling multiple scenarios for same client"""
        
        # Create client
        client_data = {
            "client_id": "888999000",
            "full_name": "Multi Scenario Test",
            "birth_date": "1965-01-01",
            "gender": "F",
            "email": "multi@example.com"
        }
        
        response = client.post("/api/v1/clients", json=client_data)
        assert response.status_code == 201
        client_id = response.json()["id"]
        
        # Create multiple scenarios
        scenarios = []
        for i in range(3):
            scenario_data = {
                "client_id": client_id,
                "name": f"Scenario {i+1}",
                "parameters": {
                    "retirement_age": 65 + i,
                    "life_expectancy": 85,
                    "initial_capital": 1000000 + (i * 100000)
                }
            }
            
            response = client.post("/api/v1/scenarios", json=scenario_data)
            assert response.status_code == 201
            scenario_id = response.json()["id"]
            scenarios.append(scenario_id)
            
            # Run each scenario
            response = client.post(f"/api/v1/scenarios/{scenario_id}/run")
            assert response.status_code == 200
        
        # Generate comprehensive report
        response = client.post(f"/api/v1/reports/client/{client_id}/comprehensive-report")
        assert response.status_code == 200
        assert len(response.content) > 1000

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
