import json
from datetime import date, datetime, timezone
from decimal import Decimal

from app.models.capital_asset import CapitalAsset
from app.models.client import Client
from app.models.scenario import Scenario
from app.services.state.effective_client_state_loader import load_effective_client_state


def _create_client(db, *, client_id: int, id_number: str) -> int:
    existing = db.query(Client).filter(Client.id == client_id).first()
    if existing is not None:
        return int(existing.id)

    client = Client(
        id=client_id,
        id_number_raw=id_number,
        id_number=id_number,
        full_name="Test User",
        birth_date=date(1980, 1, 1),
    )
    db.add(client)
    db.flush()
    return int(client.id)


def test_effective_client_state_loader_no_assets_is_pre_conversion(_test_db) -> None:
    Session = _test_db["Session"]
    with Session() as db:
        client_id = _create_client(db, client_id=910000001, id_number="910000001")
        db.commit()

        state = load_effective_client_state(db, client_id)
        assert state.client_id == client_id
        assert state.mode == "PRE_CONVERSION"
        assert isinstance(state.counts, dict)


def test_effective_client_state_loader_conversion_asset_is_post_conversion_locked(_test_db) -> None:
    Session = _test_db["Session"]
    with Session() as db:
        client_id = _create_client(db, client_id=910000002, id_number="910000002")
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
        db.commit()

        state = load_effective_client_state(db, client_id)
        assert state.mode == "POST_CONVERSION_LOCKED"
        assert state.has_any_conversion_assets is True


def test_effective_client_state_loader_snapshot_meta_transform_is_post_conversion_locked(_test_db) -> None:
    Session = _test_db["Session"]
    with Session() as db:
        client_id = _create_client(db, client_id=910000003, id_number="910000003")
        params = {
            "pension_portfolio": [],
            "_meta": {"operation_type": "TRANSFORM_FUNDS_TO_ASSETS", "trace_id": "T-1"},
        }
        scenario = Scenario(
            client_id=client_id,
            scenario_name="pension_portfolio_snapshot",
            apply_tax_planning=False,
            apply_capitalization=False,
            apply_exemption_shield=False,
            parameters=json.dumps(params, ensure_ascii=False),
            created_at=datetime.now(timezone.utc),
        )
        db.add(scenario)
        db.commit()

        state = load_effective_client_state(db, client_id)
        assert state.mode == "PRE_CONVERSION"
        assert state.last_operation_type == "TRANSFORM_FUNDS_TO_ASSETS"
        assert state.last_trace_id == "T-1"
