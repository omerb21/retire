import json
from datetime import date, datetime, timezone

from app.models.client import Client
from app.models.scenario import Scenario
from app.services.llm_chat.tool_handlers.restore_pension_portfolio_snapshot import (
    handle_restore_pension_portfolio_snapshot,
)


def test_restore_snapshot_creates_new_scenario_with_meta(db_session) -> None:
    client = db_session.query(Client).filter(Client.id_number == "910200001").first()
    if client is None:
        client = Client(
            id_number_raw="910200001",
            id_number="910200001",
            full_name="Test User",
            birth_date=date(1980, 1, 1),
        )
        db_session.add(client)
        db_session.commit()

    client_id = int(getattr(client, "id", 0) or 0)

    full_params = {
        "pension_portfolio": [
            {"account_number": "A", "balance": 100.0},
            {"account_number": "B", "balance": 0.0},
        ]
    }
    after_params = {"pension_portfolio": [{"account_number": "A", "balance": 0.0}]}

    full = Scenario(
        client_id=client_id,
        scenario_name="pension_portfolio_snapshot",
        apply_tax_planning=False,
        apply_capitalization=False,
        apply_exemption_shield=False,
        parameters=json.dumps(full_params, ensure_ascii=False),
        created_at=datetime(2025, 12, 1, tzinfo=timezone.utc),
    )
    after = Scenario(
        client_id=client_id,
        scenario_name="pension_portfolio_snapshot",
        apply_tax_planning=False,
        apply_capitalization=False,
        apply_exemption_shield=False,
        parameters=json.dumps(after_params, ensure_ascii=False),
        created_at=datetime(2025, 12, 2, tzinfo=timezone.utc),
    )

    db_session.add(full)
    db_session.add(after)
    db_session.commit()

    before_count = (
        db_session.query(Scenario)
        .filter(Scenario.client_id == client_id)
        .filter(Scenario.scenario_name == "pension_portfolio_snapshot")
        .count()
    )

    res_raw = handle_restore_pension_portfolio_snapshot(
        args={"snapshot_scenario_id": int(full.id), "safety_mode": "strict"},
        client_id=client_id,
        db=db_session,
    )
    res = json.loads(res_raw)
    assert res.get("success") is True

    after_count = (
        db_session.query(Scenario)
        .filter(Scenario.client_id == client_id)
        .filter(Scenario.scenario_name == "pension_portfolio_snapshot")
        .count()
    )
    assert after_count == before_count + 1

    restored_id = int(res.get("restored_snapshot_scenario_id") or 0)
    restored = db_session.query(Scenario).filter(Scenario.id == restored_id).first()
    assert restored is not None

    restored_params = json.loads(restored.parameters)
    assert restored_params.get("pension_portfolio") == full_params.get("pension_portfolio")

    meta = restored_params.get("_meta")
    assert isinstance(meta, dict)
    assert meta.get("operation_type") == "restore_snapshot"
    assert int(meta.get("source_snapshot_id") or 0) == int(full.id)

    # Ensure the source snapshot was not modified.
    src = db_session.query(Scenario).filter(Scenario.id == int(full.id)).first()
    assert src is not None
    assert json.loads(src.parameters) == full_params
