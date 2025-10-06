import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import patch, MagicMock
from app.main import app
from app.schemas.compare import ScenarioCompareRequest
from app.services.compare_service import compare_scenarios, _yearly_totals


client = TestClient(app)


class TestScenarioCompareSchema:
    """Test ScenarioCompareRequest schema validation"""
    
    def test_valid_request(self):
        """Test valid scenario compare request"""
        data = {
            "scenarios": [24, 25],
            "from": "2025-01",
            "to": "2025-12",
            "frequency": "monthly"
        }
        request = ScenarioCompareRequest(**data)
        assert request.scenarios == [24, 25]
        assert request.from_ == "2025-01"
        assert request.to == "2025-12"
        assert request.frequency == "monthly"
    
    def test_invalid_date_format(self):
        """Test invalid date format validation"""
        with pytest.raises(ValueError, match="from must be YYYY-MM"):
            ScenarioCompareRequest(
                scenarios=[24],
                **{"from": "2025-1", "to": "2025-12"}
            )
        
        with pytest.raises(ValueError, match="to must be YYYY-MM"):
            ScenarioCompareRequest(
                scenarios=[24],
                **{"from": "2025-01", "to": "25-12"}
            )
    
    def test_empty_scenarios_list(self):
        """Test empty scenarios list validation"""
        with pytest.raises(ValueError, match="scenarios must be a non-empty list"):
            ScenarioCompareRequest(
                scenarios=[],
                **{"from": "2025-01", "to": "2025-12"}
            )
    
    def test_invalid_scenario_ids(self):
        """Test invalid scenario IDs validation"""
        with pytest.raises(ValueError, match="scenarios must be a non-empty list of positive ints"):
            ScenarioCompareRequest(
                scenarios=[0, -1],
                **{"from": "2025-01", "to": "2025-12"}
            )


class TestCompareService:
    """Test compare_scenarios service function"""
    
    def test_yearly_totals_helper(self):
        """Test _yearly_totals helper function"""
        rows = [
            {
                "date": "2025-01-01",
                "inflow": 10000.0,
                "outflow": 5000.0,
                "additional_income_net": 2000.0,
                "capital_return_net": 500.0,
                "net": 7500.0
            },
            {
                "date": "2025-02-01", 
                "inflow": 12000.0,
                "outflow": 6000.0,
                "additional_income_net": 1500.0,
                "capital_return_net": 300.0,
                "net": 7800.0
            },
            {
                "date": "2026-01-01",
                "inflow": 15000.0,
                "outflow": 7000.0,
                "additional_income_net": 2500.0,
                "capital_return_net": 800.0,
                "net": 11300.0
            }
        ]
        
        result = _yearly_totals(rows)
        
        assert "2025" in result
        assert "2026" in result
        
        # Check 2025 totals (Jan + Feb)
        assert result["2025"]["inflow"] == 22000.0
        assert result["2025"]["outflow"] == 11000.0
        assert result["2025"]["additional_income_net"] == 3500.0
        assert result["2025"]["capital_return_net"] == 800.0
        assert result["2025"]["net"] == 15300.0
        
        # Check 2026 totals (Jan only)
        assert result["2026"]["inflow"] == 15000.0
        assert result["2026"]["net"] == 11300.0
    
    @patch('app.services.compare_service.generate_cashflow')
    def test_compare_scenarios_success(self, mock_generate_cashflow):
        """Test successful scenario comparison"""
        # Mock cashflow data for two scenarios
        mock_generate_cashflow.side_effect = [
            # Scenario 24 data
            [
                {
                    "date": "2025-01-01",
                    "inflow": 10000.0,
                    "outflow": 5000.0,
                    "additional_income_net": 2000.0,
                    "capital_return_net": 500.0,
                    "net": 7500.0
                },
                {
                    "date": "2025-02-01",
                    "inflow": 12000.0,
                    "outflow": 6000.0,
                    "additional_income_net": 1500.0,
                    "capital_return_net": 300.0,
                    "net": 7800.0
                }
            ],
            # Scenario 25 data
            [
                {
                    "date": "2025-01-01",
                    "inflow": 8000.0,
                    "outflow": 4000.0,
                    "additional_income_net": 1000.0,
                    "capital_return_net": 200.0,
                    "net": 5200.0
                },
                {
                    "date": "2025-02-01",
                    "inflow": 9000.0,
                    "outflow": 4500.0,
                    "additional_income_net": 800.0,
                    "capital_return_net": 150.0,
                    "net": 5450.0
                }
            ]
        ]
        
        mock_db = MagicMock()
        result = compare_scenarios(
            db_session=mock_db,
            client_id=1,
            scenario_ids=[24, 25],
            from_yyyymm="2025-01",
            to_yyyymm="2025-02"
        )
        
        # Verify structure
        assert "scenarios" in result
        assert "meta" in result
        assert result["meta"]["client_id"] == 1
        assert result["meta"]["from"] == "2025-01"
        assert result["meta"]["to"] == "2025-02"
        
        # Verify scenario data
        assert "24" in result["scenarios"]
        assert "25" in result["scenarios"]
        
        # Check scenario 24
        s24 = result["scenarios"]["24"]
        assert "monthly" in s24
        assert "yearly" in s24
        assert len(s24["monthly"]) == 2
        assert s24["monthly"][0]["date"] == "2025-01-01"
        assert s24["yearly"]["2025"]["net"] == 15300.0  # 7500 + 7800
        
        # Check scenario 25
        s25 = result["scenarios"]["25"]
        assert s25["yearly"]["2025"]["net"] == 10650.0  # 5200 + 5450
        
        # Verify generate_cashflow was called correctly
        assert mock_generate_cashflow.call_count == 2
        mock_generate_cashflow.assert_any_call(mock_db, 1, 24, "2025-01", "2025-02")
        mock_generate_cashflow.assert_any_call(mock_db, 1, 25, "2025-01", "2025-02")
    
    def test_compare_scenarios_invalid_frequency(self):
        """Test invalid frequency validation"""
        mock_db = MagicMock()
        
        with pytest.raises(ValueError, match="Only 'monthly' is supported"):
            compare_scenarios(
                db_session=mock_db,
                client_id=1,
                scenario_ids=[24],
                from_yyyymm="2025-01",
                to_yyyymm="2025-02",
                frequency="quarterly"
            )


class TestScenarioCompareAPI:
    """Test scenario compare API endpoint"""
    
    @patch('app.routers.scenario_compare.compare_scenarios')
    def test_compare_scenarios_endpoint_success(self, mock_compare_scenarios):
        """Test successful API call"""
        mock_compare_scenarios.return_value = {
            "meta": {
                "client_id": 1,
                "from": "2025-01",
                "to": "2025-12",
                "frequency": "monthly"
            },
            "scenarios": {
                "24": {
                    "monthly": [
                        {
                            "date": "2025-01-01",
                            "inflow": 10000.0,
                            "outflow": 5000.0,
                            "additional_income_net": 2000.0,
                            "capital_return_net": 500.0,
                            "net": 7500.0
                        }
                    ],
                    "yearly": {
                        "2025": {
                            "inflow": 120000.0,
                            "outflow": 60000.0,
                            "additional_income_net": 24000.0,
                            "capital_return_net": 6000.0,
                            "net": 90000.0
                        }
                    }
                }
            }
        }
        
        response = client.post(
            "/api/v1/clients/1/scenarios/compare",
            json={
                "scenarios": [24, 25],
                "from": "2025-01",
                "to": "2025-12",
                "frequency": "monthly"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "scenarios" in data
        assert "meta" in data
        assert data["meta"]["client_id"] == 1
        
        mock_compare_scenarios.assert_called_once()
    
    def test_compare_scenarios_endpoint_validation_error(self):
        """Test API validation errors"""
        # Test empty scenarios list
        response = client.post(
            "/api/v1/clients/1/scenarios/compare",
            json={
                "scenarios": [],
                "from": "2025-01",
                "to": "2025-12"
            }
        )
        assert response.status_code == 422
        
        # Test invalid date format
        response = client.post(
            "/api/v1/clients/1/scenarios/compare",
            json={
                "scenarios": [24],
                "from": "2025-1",
                "to": "2025-12"
            }
        )
        assert response.status_code == 422
    
    @patch('app.routers.scenario_compare.compare_scenarios')
    def test_compare_scenarios_endpoint_service_error(self, mock_compare_scenarios):
        """Test API service error handling"""
        mock_compare_scenarios.side_effect = ValueError("Invalid scenario ID")
        
        response = client.post(
            "/api/v1/clients/1/scenarios/compare",
            json={
                "scenarios": [999],
                "from": "2025-01",
                "to": "2025-12"
            }
        )
        
        assert response.status_code == 400
        assert "Invalid scenario ID" in response.text
    
    @patch('app.routers.scenario_compare.compare_scenarios')
    def test_compare_scenarios_endpoint_internal_error(self, mock_compare_scenarios):
        """Test API internal error handling"""
        mock_compare_scenarios.side_effect = Exception("Database connection failed")
        
        response = client.post(
            "/api/v1/clients/1/scenarios/compare",
            json={
                "scenarios": [24],
                "from": "2025-01",
                "to": "2025-12"
            }
        )
        
        assert response.status_code == 500
        assert "Failed to compare scenarios" in response.text
