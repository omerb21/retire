import json
from datetime import date
from decimal import Decimal

from app.models.capital_asset import CapitalAsset
from app.models.client import Client
from app.models.scenario import Scenario
from app.services.state.effective_client_state_loader import load_effective_client_state


def test_effective_state_restore_snapshot_unlocks_post_conversion(_test_db) -> None:
    Session = _test_db["Session"]
    with Session() as db:
        client = db.query(Client).filter(Client.id == 920100001).first()
        if client is None:
            client = Client(
                id=920100001,
                id_number_raw="920100001",
                id_number="920100001",
                full_name="Test User",
                birth_date=date(1980, 1, 1),
            )
            db.add(client)
            db.flush()
        client_id = int(getattr(client, "id", 0) or 0)

        # Create conversion-looking assets that would normally trigger POST_CONVERSION_LOCKED
        asset = CapitalAsset(
            client_id=client_id,
            asset_name="Converted",
            asset_type="provident_fund",
            current_value=Decimal("0"),
            monthly_income=Decimal("0"),
            annual_return_rate=Decimal("0.04"),
            payment_frequency="annually",
            start_date=date(2020, 1, 1),
            indexation_method="none",
            tax_treatment="taxable",
            conversion_source=json.dumps({"source": "scenario_conversion"}, ensure_ascii=False),
        )
        db.add(asset)

        # Latest snapshot indicates restore_snapshot -> must unlock regardless of conversion assets
        snapshot_params = {
            "pension_portfolio": [{"account_number": "A", "יתרה": 100}],
            "_meta": {"operation_type": "restore_snapshot", "trace_id": "t"},
        }
        snapshot = Scenario(
            client_id=client_id,
            scenario_name="pension_portfolio_snapshot",
            apply_tax_planning=False,
            apply_capitalization=False,
            apply_exemption_shield=False,
            parameters=json.dumps(snapshot_params, ensure_ascii=False),
        )
        db.add(snapshot)
        db.commit()

        state = load_effective_client_state(db, client_id)
        assert state.mode == "PRE_CONVERSION"
        assert state.unlock_reason == "restore_snapshot"
        assert state.has_any_conversion_assets is True
