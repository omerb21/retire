import json
from datetime import datetime, timezone

from app.models.scenario import Scenario
from app.services.pension_portfolio.snapshot_loader import (
    dedupe_pension_portfolio_snapshot,
)
from tests.warnings_guard import capture_identity_map_sawarnings


def test_snapshot_loader_dedupe_has_no_identity_map_replacement_warning(
    db_session, client
):
    snapshot1 = Scenario(
        client_id=client.id,
        scenario_name="pension_portfolio_snapshot",
        apply_tax_planning=False,
        apply_capitalization=False,
        apply_exemption_shield=False,
        parameters=json.dumps({"pension_portfolio": []}, ensure_ascii=False),
        created_at=datetime.now(timezone.utc),
    )
    snapshot2 = Scenario(
        client_id=client.id,
        scenario_name="pension_portfolio_snapshot",
        apply_tax_planning=False,
        apply_capitalization=False,
        apply_exemption_shield=False,
        parameters=json.dumps({"pension_portfolio": []}, ensure_ascii=False),
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(snapshot1)
    db_session.add(snapshot2)
    db_session.commit()

    with capture_identity_map_sawarnings() as messages:
        dedupe_pension_portfolio_snapshot(db_session, client.id)

    assert all(
        "Identity map already had an identity for" not in msg for msg in messages
    ), messages
