import json
from datetime import datetime, timedelta, timezone

 from datetime import date

 from app.models.client import Client
from app.models.scenario import Scenario
from app.services.pension_portfolio.snapshot_loader import (
    load_latest_pension_portfolio_snapshot,
)


def test_snapshot_loader_ignores_non_snapshot_scenarios(db_session, client):
    dedicated = Client(
        id_number="999999999",
        id_number_raw="999999999",
        full_name="Snapshot Loader Test",
        first_name="Snapshot",
        last_name="Loader",
        birth_date=date(1980, 1, 1),
        gender="male",
        marital_status="single",
        self_employed=False,
        current_employer_exists=False,
        is_active=True,
    )
    db_session.add(dedicated)
    db_session.commit()

    partial_accounts = [
        {
            "מספר_חשבון": "A1",
            "שם_תכנית": "Partial",
            "חברה_מנהלת": "X",
            "סוג_מוצר": "קרן השתלמות",
            "יתרה": 1000,
        },
        {
            "מספר_חשבון": "A2",
            "שם_תכנית": "Partial2",
            "חברה_מנהלת": "X",
            "סוג_מוצר": "קרן השתלמות",
            "יתרה": 2000,
        },
    ]

    full_accounts = [
        {
            "מספר_חשבון": f"F{i}",
            "שם_תכנית": f"Full{i}",
            "חברה_מנהלת": "Y",
            "סוג_מוצר": "קופת גמל",
            "יתרה": 10000 + i,
        }
        for i in range(9)
    ]

    newer_other = Scenario(
        client_id=dedicated.id,
        scenario_name="retirement_projection",
        apply_tax_planning=False,
        apply_capitalization=False,
        apply_exemption_shield=False,
        parameters=json.dumps({"pension_portfolio": partial_accounts}, ensure_ascii=False),
        created_at=datetime.now(timezone.utc) + timedelta(minutes=1),
    )

    snapshot = Scenario(
        client_id=dedicated.id,
        scenario_name="pension_portfolio_snapshot",
        apply_tax_planning=False,
        apply_capitalization=False,
        apply_exemption_shield=False,
        parameters=json.dumps({"pension_portfolio": full_accounts}, ensure_ascii=False),
        created_at=datetime.now(timezone.utc),
    )

    db_session.add(newer_other)
    db_session.add(snapshot)
    db_session.commit()

    loaded = load_latest_pension_portfolio_snapshot(db_session, dedicated.id)
    assert loaded is not None

    portfolio, _snapshot_at = loaded
    assert isinstance(portfolio, list)
    assert len(portfolio) == 9
