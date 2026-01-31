import json
from datetime import date

from fastapi.testclient import TestClient

from app.main import app
from app.models.client import Client
from app.models.pension_fund import PensionFund
from app.models.scenario import Scenario


def test_pension_portfolio_convert_uses_saved_selection(_test_db) -> None:
    Session = _test_db["Session"]

    with Session() as db:
        client = Client(
            id_number_raw="990000039",
            id_number="990000039",
            full_name="Convert Portfolio Test",
            birth_date=date(1980, 1, 1),
            gender="male",
        )
        db.add(client)
        db.flush()
        client_id = int(getattr(client, "id", 0) or 0)

        account_number = "494930"
        portfolio = [
            {
                "מספר_חשבון": account_number,
                "שם_תכנית": "כלל תמר",
                "חברה_מנהלת": "כלל",
                "סוג_מוצר": "קופת גמל",
                "יתרה": 100.0,
                "selected_amounts": {
                    "פיצויים_ממעסיקים_קודמים_רצף_קצבה": 10.0,
                    "תגמולי_עובד_אחרי_2000": 20.0,
                    "תגמולי_מעביד_אחרי_2000": 30.0,
                },
            }
        ]

        db.query(Scenario).filter(
            Scenario.client_id == client_id,
            Scenario.scenario_name == "pension_portfolio_snapshot",
        ).delete(synchronize_session=False)

        db.query(PensionFund).filter(
            PensionFund.client_id == client_id,
            PensionFund.deduction_file == account_number,
        ).delete(synchronize_session=False)

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

    resp = api.post(
        f"/api/v1/clients/{client_id}/pension-portfolio/convert",
        json={"conversion_mode": "assets"},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload.get("success") is True
    assert int(payload.get("converted_count") or 0) > 0

    with Session() as db:
        created = (
            db.query(PensionFund)
            .filter(PensionFund.client_id == client_id)
            .filter(PensionFund.deduction_file == account_number)
            .all()
        )
        assert created
