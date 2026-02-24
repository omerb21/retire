import json

from app.models.scenario import Scenario


def test_pension_portfolio_gap_is_consistent_when_row_is_zeroed(
    db_session, client
) -> None:
    account_number = "ACC-GAP-0"

    db_session.query(Scenario).filter(
        Scenario.client_id == client.id,
        Scenario.scenario_name == "pension_portfolio_snapshot",
    ).delete(synchronize_session=False)
    db_session.commit()

    portfolio = [
        {
            "מספר_חשבון": account_number,
            "שם_תכנית": "Test Plan",
            "סוג_מוצר": "קופת גמל",
            "יתרה": 0.0,
            "סך_רכיבים": 0.0,
            "פער_יתרה_מול_רכיבים": -123.45,
            "תגמולי_עובד_אחרי_2000": 0.0,
            "תגמולי_מעביד_אחרי_2000": 0.0,
        }
    ]

    snapshot = Scenario(
        client_id=client.id,
        scenario_name="pension_portfolio_snapshot",
        apply_tax_planning=False,
        apply_capitalization=False,
        apply_exemption_shield=False,
        parameters=json.dumps({"pension_portfolio": portfolio}, ensure_ascii=False),
    )
    db_session.add(snapshot)
    db_session.commit()

    resp = client.get(f"/api/v1/clients/{client.id}/pension-portfolio/")
    assert resp.status_code == 200
    returned = resp.json()
    assert isinstance(returned, list)

    row = next(
        (
            r
            for r in returned
            if isinstance(r, dict) and r.get("מספר_חשבון") == account_number
        ),
        None,
    )
    assert row is not None

    assert float(row.get("יתרה") or 0) == 0.0
    assert float(row.get("סך_רכיבים") or 0) == 0.0
    assert float(row.get("פער_יתרה_מול_רכיבים") or 0) == 0.0
