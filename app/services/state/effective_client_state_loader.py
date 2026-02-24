from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy.orm import Session

from app.models.capital_asset import CapitalAsset
from app.models.pension_fund import PensionFund
from app.models.scenario import Scenario
from app.services.state.effective_client_state import EffectiveClientState


def _looks_like_conversion_asset(
    *, conversion_source_raw: str | None, remarks: str | None
) -> tuple[bool, bool]:
    has_conversion = False
    has_commutation = False

    raw = conversion_source_raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = None

        if isinstance(parsed, dict):
            try:
                src = str(parsed.get("source") or "").strip()
            except Exception:
                src = ""
            if src == "scenario_conversion":
                has_conversion = True

            try:
                typ = str(parsed.get("type") or "").strip()
            except Exception:
                typ = ""
            if typ in {"funds_to_assets_conversion", "pension_commutation"}:
                has_conversion = True
            if typ == "pension_commutation":
                has_commutation = True
        else:
            lowered_raw = raw.lower()
            if "scenario_conversion" in lowered_raw:
                has_conversion = True
            if "pension_commutation" in lowered_raw:
                has_conversion = True
                has_commutation = True
            if "funds_to_assets_conversion" in lowered_raw:
                has_conversion = True

    remarks_raw = remarks if isinstance(remarks, str) else ""
    if remarks_raw:
        if remarks_raw.startswith("COMMUTATION:"):
            has_conversion = True
            has_commutation = True
        if "scenario_conversion" in remarks_raw:
            has_conversion = True

    return has_conversion, has_commutation


def _is_portfolio_import_conversion_source(conversion_source_raw: str | None) -> bool:
    if not isinstance(conversion_source_raw, str):
        return False
    raw = conversion_source_raw.strip()
    if not raw:
        return False
    # Portfolio snapshot imports are not considered "post conversion" outputs.
    # They represent raw sources that may exist transiently in DB but should not lock planning.
    return (
        '"source": "pension_portfolio"' in raw
        or '"type": "pension_portfolio"' in raw
        or '"source": "pension_portfolio_convert"' in raw
    )


def load_effective_client_state(db: Session, client_id: int) -> EffectiveClientState:
    capital_assets_count = int(
        db.query(CapitalAsset).filter(CapitalAsset.client_id == client_id).count()
    )
    pension_funds_count = int(
        db.query(PensionFund).filter(PensionFund.client_id == client_id).count()
    )
    snapshots_count = int(
        db.query(Scenario)
        .filter(Scenario.client_id == client_id)
        .filter(Scenario.scenario_name == "pension_portfolio_snapshot")
        .count()
    )

    latest_snapshot = (
        db.query(Scenario)
        .filter(Scenario.client_id == client_id)
        .filter(Scenario.scenario_name == "pension_portfolio_snapshot")
        .order_by(Scenario.created_at.desc())
        .first()
    )

    latest_snapshot_id = (
        getattr(latest_snapshot, "id", None) if latest_snapshot is not None else None
    )
    latest_snapshot_at_utc = None
    last_state_change_at_utc = None
    last_operation_type = None
    last_trace_id = None

    if latest_snapshot is not None:
        created_at = getattr(latest_snapshot, "created_at", None)
        if isinstance(created_at, datetime):
            if created_at.tzinfo is None:
                latest_snapshot_at_utc = created_at.replace(tzinfo=timezone.utc)
            else:
                latest_snapshot_at_utc = created_at.astimezone(timezone.utc)

        try:
            params = (
                json.loads(latest_snapshot.parameters)
                if latest_snapshot.parameters
                else {}
            )
        except Exception:
            params = {}

        meta = params.get("_meta") if isinstance(params, dict) else None
        if isinstance(meta, dict):
            last_operation_type = meta.get("operation_type")
            last_trace_id = meta.get("trace_id")
            if latest_snapshot_at_utc is not None:
                last_state_change_at_utc = latest_snapshot_at_utc

    # SSOT for "post conversion": only count user-visible outputs.
    # Ignore portfolio-import rows (conversion_source indicates pension_portfolio).
    has_any_capital_assets = False
    has_any_pension_funds = False
    try:
        for asset in (
            db.query(CapitalAsset).filter(CapitalAsset.client_id == client_id).all()
            or []
        ):
            if _is_portfolio_import_conversion_source(
                getattr(asset, "conversion_source", None)
            ):
                continue
            has_any_capital_assets = True
            break
    except Exception:
        has_any_capital_assets = bool(capital_assets_count > 0)

    try:
        for pf in (
            db.query(PensionFund).filter(PensionFund.client_id == client_id).all() or []
        ):
            if _is_portfolio_import_conversion_source(
                getattr(pf, "conversion_source", None)
            ):
                continue
            has_any_pension_funds = True
            break
    except Exception:
        has_any_pension_funds = bool(pension_funds_count > 0)
    has_any_conversion_assets = False
    has_any_commutation_assets = False

    try:
        conversion_candidates = (
            db.query(CapitalAsset)
            .filter(CapitalAsset.client_id == client_id)
            .filter(
                (CapitalAsset.conversion_source.isnot(None))
                | (CapitalAsset.remarks.isnot(None))
            )
            .all()
        )
    except Exception:
        conversion_candidates = []

    for asset in conversion_candidates:
        conv, comm = _looks_like_conversion_asset(
            conversion_source_raw=getattr(asset, "conversion_source", None),
            remarks=getattr(asset, "remarks", None),
        )
        if conv:
            has_any_conversion_assets = True
        if comm:
            has_any_commutation_assets = True
        if has_any_conversion_assets and has_any_commutation_assets:
            break

    mode: Literal["PRE_CONVERSION", "POST_CONVERSION_LOCKED"]
    # SSOT: the effective mode is determined strictly by current DB state.
    # If the DB has no (user-visible) pension funds and no (user-visible) capital assets, the system is considered reset.
    mode = (
        "POST_CONVERSION_LOCKED"
        if (has_any_capital_assets or has_any_pension_funds)
        else "PRE_CONVERSION"
    )

    return EffectiveClientState(
        client_id=int(client_id),
        mode=mode,
        unlock_reason=None,
        last_state_change_at_utc=last_state_change_at_utc,
        last_operation_type=last_operation_type,
        last_trace_id=last_trace_id,
        counts={
            "capital_assets_count": capital_assets_count,
            "pension_funds_count": pension_funds_count,
            "snapshots_count": snapshots_count,
        },
        has_any_conversion_assets=bool(has_any_conversion_assets),
        has_any_commutation_assets=bool(has_any_commutation_assets),
        has_any_capital_assets=bool(has_any_capital_assets),
        latest_snapshot_id=latest_snapshot_id,
        latest_snapshot_at_utc=latest_snapshot_at_utc,
    )
