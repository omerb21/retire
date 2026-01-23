import json
from datetime import date

from fastapi.testclient import TestClient

from app.main import app
from app.models.client import Client


def test_pension_portfolio_save_accepts_accounts_wrapper_payload(_test_db) -> None:
    Session = _test_db["Session"]

    with Session() as db:
        client = Client(
            id_number_raw="991000003",
            id_number="991000003",
            full_name="Test User",
            birth_date=date(1980, 1, 1),
            gender="male",
        )
        db.add(client)
        db.flush()
        client_id = int(getattr(client, "id", 0) or 0)
        db.commit()

    api = TestClient(app)

    payload = {
        "accounts": [
            {
                "מספר_חשבון": "ACC-1",
                "שם_תכנית": "Test Plan",
                "סוג_מוצר": "קופת גמל",
                "יתרה": 123.0,
            }
        ]
    }

    save_resp = api.post(
        f"/api/v1/clients/{client_id}/pension-portfolio/save",
        json=payload,
    )
    assert save_resp.status_code == 200

    body = save_resp.json()
    assert body.get("accounts_count") == 1
    assert body.get("kept_snapshot_id") is not None
    assert body.get("dedupe_deleted_count") is not None
