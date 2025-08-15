import uuid
from datetime import date
from fastapi.testclient import TestClient
from app.main import app as fastapi_app
from app.models import Client

class TestPensionFundAPI:
    def test_create_and_compute_fund(self, db_session):
        client = TestClient(fastapi_app)

        # יצירת לקוח לטסט
        from tests.utils import gen_valid_id
        unique_suffix = str(uuid.uuid4())[:8]
        id_number = gen_valid_id()
        email = f"test_{unique_suffix}@test.com"
        
        test_client = Client(
            id_number_raw=id_number,
            id_number=id_number,
            full_name="ישראל ישראלי",
            birth_date=date(1980,1,1),
            email=email,
            phone="0500000000",
            is_active=True
        )
        db_session.add(test_client)
        db_session.commit()
        db_session.refresh(test_client)

        # יצירת מקור קצבה במצב calculated
        payload = {
            "client_id": test_client.id,
            "fund_name": "קרן פנסיה",
            "fund_type": "retirement",
            "input_mode": "calculated",
            "balance": 120000.0,
            "annuity_factor": 200.0,
            "indexation_method": "fixed",
            "fixed_index_rate": 0.02
        }
        r = client.post(f"/api/v1/clients/{test_client.id}/pension-funds", json=payload)
        assert r.status_code == 201, r.text
        fund = r.json()
        fund_id = fund["id"]

        # חישוב ועדכון
        r = client.post(f"/api/v1/pension-funds/{fund_id}/compute")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["pension_amount"] == 600.0
        assert round(data["indexed_pension_amount"], 2) == 612.0
