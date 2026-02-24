import json

from app.models.scenario import Scenario
from app.services.pension_portfolio.snapshot_loader import upsert_snapshot
from app.services.llm_chat.tool_handlers.transform_funds_conversion import (
    _create_updated_snapshot_scenario,
)


def test_snapshot_two_writes_keep_single_row(db_session, client) -> None:
    client_id = int(getattr(client, "id", 0) or 0)

    db_session.query(Scenario).filter(Scenario.client_id == client_id).filter(
        Scenario.scenario_name == "pension_portfolio_snapshot"
    ).delete(synchronize_session=False)
    db_session.commit()

    upsert_snapshot(
        db_session,
        client_id,
        [{"account_number": "A", "balance": 1.0}],
        meta={"operation_type": "portfolio_import"},
    )
    db_session.commit()

    upsert_snapshot(
        db_session,
        client_id,
        [{"account_number": "B", "balance": 2.0}],
        meta={"operation_type": "portfolio_import"},
    )
    db_session.commit()

    rows = (
        db_session.query(Scenario)
        .filter(Scenario.client_id == client_id)
        .filter(Scenario.scenario_name == "pension_portfolio_snapshot")
        .all()
    )
    assert len(rows) == 1


def test_snapshot_transform_updates_operation_type_and_keeps_single_row(
    db_session, client
) -> None:
    client_id = int(getattr(client, "id", 0) or 0)

    db_session.query(Scenario).filter(Scenario.client_id == client_id).filter(
        Scenario.scenario_name == "pension_portfolio_snapshot"
    ).delete(synchronize_session=False)
    db_session.commit()

    upsert_snapshot(
        db_session,
        client_id,
        [{"account_number": "A", "balance": 10.0}],
        meta={"operation_type": "portfolio_import"},
    )
    db_session.commit()

    ok, updated = _create_updated_snapshot_scenario(
        db=db_session,
        client_id=client_id,
        deltas={},
        trace_id="t1",
        operation_type="TRANSFORM_FUNDS_TO_ASSETS",
    )
    assert ok is True
    assert updated == 1
    db_session.commit()

    rows = (
        db_session.query(Scenario)
        .filter(Scenario.client_id == client_id)
        .filter(Scenario.scenario_name == "pension_portfolio_snapshot")
        .all()
    )
    assert len(rows) == 1

    params = json.loads(rows[0].parameters)
    meta = params.get("_meta")
    assert isinstance(meta, dict)
    assert meta.get("operation_type") == "TRANSFORM_FUNDS_TO_ASSETS"
