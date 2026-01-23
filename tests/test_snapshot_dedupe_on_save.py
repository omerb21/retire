import json
from datetime import date

from fastapi.testclient import TestClient

from app.main import app
from app.models.client import Client
from app.models.scenario import Scenario


def test_save_dedupes_multiple_snapshot_rows(_test_db) -> None:
    Session = _test_db["Session"]

    with Session() as db:
        client = Client(
            id_number_raw="991000001",
            id_number="991000001",
            full_name="Test User",
            birth_date=date(1980, 1, 1),
            gender="male",
        )
        db.add(client)
        db.flush()
        client_id = int(getattr(client, "id", 0) or 0)

        for i in range(3):
            sc = Scenario(
                client_id=client_id,
                scenario_name="pension_portfolio_snapshot",
                apply_tax_planning=False,
                apply_capitalization=False,
                apply_exemption_shield=False,
                parameters=json.dumps({"pension_portfolio": [{"account_number": f"A{i}"}]}, ensure_ascii=False),
            )
            db.add(sc)
        db.commit()

        assert (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "pension_portfolio_snapshot")
            .count()
            == 3
        )

    api = TestClient(app)
    resp = api.post(
        f"/api/v1/clients/{client_id}/pension-portfolio/save",
        json={"accounts": [{"account_number": "X", "balance": 1.0}]},
    )
    assert resp.status_code == 200
    payload = resp.json()

    assert int(payload.get("dedupe_deleted_count") or 0) == 2
    kept_id = int(payload.get("kept_snapshot_id") or 0)
    assert kept_id > 0

    with Session() as db:
        rows = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "pension_portfolio_snapshot")
            .all()
        )
        assert len(rows) == 1
        assert int(getattr(rows[0], "id", 0) or 0) == kept_id
