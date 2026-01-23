import json
from datetime import date

from fastapi.testclient import TestClient

from app.main import app
from app.models.client import Client
from app.models.scenario import Scenario


def test_pension_portfolio_save_accepts_list_payload(_test_db) -> None:
    Session = _test_db["Session"]

    with Session() as db:
        client = Client(
            id_number_raw="991000002",
            id_number="991000002",
            full_name="Test User",
            birth_date=date(1980, 1, 1),
            gender="male",
        )
        db.add(client)
        db.flush()
        client_id = int(getattr(client, "id", 0) or 0)

        portfolio = [
            {
                "מספר_חשבון": "ACC-1",
                "שם_תכנית": "Test Plan",
                "סוג_מוצר": "קופת גמל",
                "יתרה": 123.0,
            }
        ]
        snapshot = Scenario(
            client_id=client_id,
            scenario_name="pension_portfolio_snapshot",
            apply_tax_planning=False,
            apply_capitalization=False,
            apply_exemption_shield=False,
            parameters=json.dumps({"pension_portfolio": portfolio}, ensure_ascii=False),
        )
        db.add(snapshot)
        db.commit()

    api = TestClient(app)

    get_resp = api.get(f"/api/v1/clients/{client_id}/pension-portfolio/")
    assert get_resp.status_code == 200
    accounts = get_resp.json()
    assert isinstance(accounts, list)

    save_resp = api.post(
        f"/api/v1/clients/{client_id}/pension-portfolio/save",
        json=accounts,
    )
    assert save_resp.status_code == 200

    payload = save_resp.json()
    assert payload.get("kept_snapshot_id") is not None
    assert payload.get("dedupe_deleted_count") is not None
