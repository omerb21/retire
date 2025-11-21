"""Tests for cashflow generation functionality."""

import pytest
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.services.cashflow_service import generate_cashflow
from tests.conftest import test_client, db_session, test_client_data


class TestCashflowGeneration:
    """Test cashflow generation service and API."""

    def test_generate_ok_monthly_12_rows(self, db_session: Session, test_client_data):
        """Test successful generation of 12 monthly rows."""
        client_id = test_client_data["id"]
        scenario_id = 24  # Using default scenario ID
        
        # Generate cashflow for 12 months
        result = generate_cashflow(
            db=db_session,
            client_id=client_id,
            scenario_id=scenario_id,
            start_ym="2025-01",
            end_ym="2025-12",
            frequency="monthly"
        )
        
        # Verify 12 rows returned
        assert len(result) == 12
        
        # Verify each row has all required fields
        required_fields = ["date", "inflow", "outflow", "additional_income_net", "capital_return_net", "net"]
        for row in result:
            for field in required_fields:
                assert field in row
                if field == "date":
                    # Allow date to be either a date object or ISO string ("YYYY-MM-01")
                    assert isinstance(row[field], (date, str))
                else:
                    assert isinstance(row[field], (int, float, date))
        
        # Verify dates are first of month and sequential
        expected_dates = [
            date(2025, 1, 1), date(2025, 2, 1), date(2025, 3, 1), date(2025, 4, 1),
            date(2025, 5, 1), date(2025, 6, 1), date(2025, 7, 1), date(2025, 8, 1),
            date(2025, 9, 1), date(2025, 10, 1), date(2025, 11, 1), date(2025, 12, 1)
        ]
        # Normalize result dates: convert ISO strings back to date objects if needed
        actual_dates = [
            date.fromisoformat(row["date"]) if isinstance(row["date"], str) else row["date"]
            for row in result
        ]
        assert actual_dates == expected_dates

    def test_generate_bad_range(self, db_session: Session, test_client_data):
        """Test error when from > to."""
        client_id = test_client_data["id"]
        scenario_id = 24
        
        with pytest.raises(ValueError, match="'from' date must be less than or equal to 'to' date"):
            generate_cashflow(
                db=db_session,
                client_id=client_id,
                scenario_id=scenario_id,
                start_ym="2025-12",
                end_ym="2025-01",
                frequency="monthly"
            )

    def test_generate_bad_frequency(self, db_session: Session, test_client_data):
        """Test error when frequency is not monthly."""
        client_id = test_client_data["id"]
        scenario_id = 24
        
        with pytest.raises(ValueError, match="supported: monthly"):
            generate_cashflow(
                db=db_session,
                client_id=client_id,
                scenario_id=scenario_id,
                start_ym="2025-01",
                end_ym="2025-12",
                frequency="weekly"
            )


class TestCashflowAPI:
    """Test cashflow generation API endpoints."""

    def _create_api_client(self, test_client: TestClient) -> int:
        """Create a test client via the public API and return its ID.

        This ensures the cashflow endpoint sees the same DB state as the
        client creation endpoint, instead of relying on ORM fixtures that
        run in separate transactions.
        """
        from datetime import date, timedelta
        import random
        from tests.utils import gen_valid_id

        unique_id = gen_valid_id()
        unique_email = f"test{random.randint(1000, 9999)}@example.com"

        payload = {
            "id_number_raw": unique_id,
            "id_number": unique_id,
            "full_name": "ישראל ישראלי",
            "first_name": "ישראל",
            "last_name": "ישראלי",
            "birth_date": (date.today() - timedelta(days=30 * 365)).isoformat(),
            "gender": "male",
            "marital_status": "single",
            "self_employed": False,
            "current_employer_exists": True,
            "planned_termination_date": (date.today() + timedelta(days=365)).isoformat(),
            "email": unique_email,
            "phone": "050-1234567",
            "address_street": "רחוב הרצל 1",
            "address_city": "תל אביב",
            "address_postal_code": "12345",
            "retirement_target_date": (date.today() + timedelta(days=35 * 365)).isoformat(),
            "is_active": True,
            "notes": "הערות לקוח",
        }

        response = test_client.post("/api/v1/clients", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        return data["id"]

    def test_api_generate_ok(self, test_client: TestClient):
        """Test successful API call."""
        client_id = self._create_api_client(test_client)
        scenario_id = 24
        
        response = test_client.post(
            f"/api/v1/scenarios/{scenario_id}/cashflow/generate?client_id={client_id}",
            json={
                "from": "2025-01",
                "to": "2025-12",
                "frequency": "monthly"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 12
        
        # Verify structure of first row
        first_row = data[0]
        required_fields = ["date", "inflow", "outflow", "additional_income_net", "capital_return_net", "net"]
        for field in required_fields:
            assert field in first_row

    def test_api_bad_range_400(self, test_client: TestClient):
        """Test API returns 400 for bad date range."""
        client_id = self._create_api_client(test_client)
        scenario_id = 24
        
        response = test_client.post(
            f"/api/v1/scenarios/{scenario_id}/cashflow/generate?client_id={client_id}",
            json={
                "from": "2025-12",
                "to": "2025-01",
                "frequency": "monthly"
            }
        )
        
        assert response.status_code == 400
        assert "from" in response.json()["detail"].lower()

    def test_api_bad_frequency_422(self, test_client: TestClient):
        """Test API returns 422 for unsupported frequency."""
        client_id = self._create_api_client(test_client)
        scenario_id = 24
        
        response = test_client.post(
            f"/api/v1/scenarios/{scenario_id}/cashflow/generate?client_id={client_id}",
            json={
                "from": "2025-01",
                "to": "2025-12",
                "frequency": "weekly"
            }
        )
        
        assert response.status_code == 422
        detail = response.json()["detail"]
        # Check if it's a validation error (422) or our custom error
        if isinstance(detail, list):
            # Pydantic validation error
            assert any("weekly" in str(error) for error in detail)
        else:
            # Our custom error
            assert "supported: monthly" in detail

    def test_api_invalid_date_format_422(self, test_client: TestClient):
        """Test API returns 422 for invalid date format."""
        client_id = self._create_api_client(test_client)
        scenario_id = 24
        
        response = test_client.post(
            f"/api/v1/scenarios/{scenario_id}/cashflow/generate?client_id={client_id}",
            json={
                "from": "2025/01",  # Invalid format
                "to": "2025-12",
                "frequency": "monthly"
            }
        )
        
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert isinstance(detail, list)  # Pydantic validation error
