"""Tests for POST /api/v1/clients/{client_id}/cashflow/integrate-all.

Covers:
  1. List format (existing) -> 200
  2. Envelope format (monthly) -> 200
  3. Empty monthly -> 422 with detail
"""

import pytest
from datetime import date, timedelta
import random
from fastapi.testclient import TestClient

from tests.conftest import test_client


def _create_api_client(tc: TestClient) -> int:
    """Create a test client via the public API and return its ID."""
    from tests.utils import gen_valid_id

    unique_id = gen_valid_id()
    unique_email = f"test{random.randint(10000, 99999)}@example.com"

    payload = {
        "id_number_raw": unique_id,
        "id_number": unique_id,
        "full_name": "Test Integrate",
        "first_name": "Test",
        "last_name": "Integrate",
        "birth_date": (date.today() - timedelta(days=30 * 365)).isoformat(),
        "gender": "male",
        "marital_status": "single",
        "self_employed": False,
        "current_employer_exists": True,
        "planned_termination_date": (date.today() + timedelta(days=365)).isoformat(),
        "email": unique_email,
        "phone": "050-0000000",
        "address_street": "Test 1",
        "address_city": "Test City",
        "address_postal_code": "00000",
        "retirement_target_date": (date.today() + timedelta(days=35 * 365)).isoformat(),
        "is_active": True,
        "notes": "",
    }

    response = tc.post("/api/v1/clients", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["id"]


class TestIntegrateAllListFormat:
    """POST integrate-all with the existing list format."""

    def test_list_format_200(self, test_client: TestClient):
        client_id = _create_api_client(test_client)
        cashflow_list = [
            {"date": "2025-06-01", "inflow": 10000, "outflow": 3000, "net": 7000},
            {"date": "2025-07-01", "inflow": 10000, "outflow": 3000, "net": 7000},
        ]
        resp = test_client.post(
            f"/api/v1/clients/{client_id}/cashflow/integrate-all",
            json=cashflow_list,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 2


class TestIntegrateAllEnvelopeFormat:
    """POST integrate-all with the envelope (monthly) format."""

    def test_envelope_format_200(self, test_client: TestClient):
        client_id = _create_api_client(test_client)
        envelope = {
            "monthly": [
                {"date": "2025-06-01", "income": 10000, "expenses": 3000, "net": 7000},
                {"date": "2025-07-01", "income": 10000, "expenses": 3000, "net": 7000},
            ]
        }
        resp = test_client.post(
            f"/api/v1/clients/{client_id}/cashflow/integrate-all",
            json=envelope,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 2

    def test_envelope_empty_monthly_422(self, test_client: TestClient):
        client_id = _create_api_client(test_client)
        envelope = {"monthly": []}
        resp = test_client.post(
            f"/api/v1/clients/{client_id}/cashflow/integrate-all",
            json=envelope,
        )
        assert resp.status_code == 422, resp.text
        body = resp.json()
        assert "detail" in body
        # detail may be a string (our HTTPException) or a list (Pydantic)
        detail = body["detail"]
        if isinstance(detail, str):
            assert "empty" in detail.lower()
        else:
            # Pydantic validation list – at least one error present
            assert len(detail) >= 1
