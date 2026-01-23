import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.scenario import Scenario
from app.models.capital_asset import CapitalAsset
from app.models.pension_fund import PensionFund
from app.schemas.llm_chat import PensionPortfolioAccount


def upsert_snapshot(
    db: Session,
    client_id: int,
    pension_portfolio: list[dict[str, Any]],
    meta: dict[str, Any] | None = None,
) -> Scenario:
    snapshots = (
        db.query(Scenario)
        .filter(Scenario.client_id == client_id)
        .filter(Scenario.scenario_name == "pension_portfolio_snapshot")
        .order_by(Scenario.id.desc())
        .all()
    )

    keep: Scenario | None = snapshots[0] if snapshots else None
    if keep is None:
        keep = Scenario(
            client_id=client_id,
            scenario_name="pension_portfolio_snapshot",
            apply_tax_planning=False,
            apply_capitalization=False,
            apply_exemption_shield=False,
            parameters=json.dumps(
                {"pension_portfolio": pension_portfolio or [], "_meta": dict(meta or {})},
                ensure_ascii=False,
            ),
        )
        db.add(keep)
        db.flush()
        return keep

    if len(snapshots) > 1:
        keep_id = int(getattr(keep, "id", 0) or 0)
        to_delete = [int(getattr(s, "id", 0) or 0) for s in snapshots[1:]]
        to_delete = [sid for sid in to_delete if sid and sid != keep_id]
        if to_delete:
            db.query(Scenario).filter(Scenario.id.in_(to_delete)).delete(
                synchronize_session=False
            )

    try:
        params = json.loads(keep.parameters) if keep.parameters else {}
    except Exception:
        params = {}
    if not isinstance(params, dict):
        params = {}

    params["pension_portfolio"] = pension_portfolio or []

    if meta is not None:
        existing_meta = params.get("_meta")
        merged_meta: dict[str, Any] = dict(existing_meta) if isinstance(existing_meta, dict) else {}
        for k, v in dict(meta).items():
            merged_meta[str(k)] = v
        params["_meta"] = merged_meta

    keep.parameters = json.dumps(params, ensure_ascii=False)
    db.add(keep)
    db.flush()
    return keep


def load_latest_pension_portfolio_snapshot(
    db: Session,
    client_id: int,
    *,
    lookback_scenarios: int = 20,
) -> tuple[list[dict[str, Any]], str] | None:
    scenarios = (
        db.query(Scenario)
        .filter(Scenario.client_id == client_id)
        .filter(Scenario.scenario_name == "pension_portfolio_snapshot")
        .order_by(Scenario.created_at.desc())
        .limit(int(lookback_scenarios))
        .all()
    )

    for scenario in scenarios:
        if not scenario.parameters:
            continue
        try:
            params = json.loads(scenario.parameters)
        except Exception:
            continue
        portfolio = params.get("pension_portfolio")
        if isinstance(portfolio, list):
            snapshot_at = ""
            try:
                snapshot_at = scenario.created_at.isoformat()
            except Exception:
                snapshot_at = ""
            normalized: list[dict[str, Any]] = []
            for item in portfolio:
                if not isinstance(item, dict):
                    continue
                product_type = (
                    item.get("סוג_מוצר")
                    or item.get("product_type")
                    or item.get("סוג מוצר")
                    or ""
                )
                lowered_product_type = str(product_type).lower()
                is_education_fund = (
                    ("השתלמות" in lowered_product_type)
                    or ("education_fund" in lowered_product_type)
                    or ("klal_stud" in lowered_product_type)
                )
                if is_education_fund:
                    existing_edu_val = item.get("קרן_השתלמות")
                    try:
                        existing_edu_num = float(existing_edu_val or 0)
                    except (TypeError, ValueError):
                        existing_edu_num = 0.0
                    if existing_edu_num <= 0:
                        candidate_vals = [
                            item.get("יתרה"),
                            item.get("balance"),
                            item.get("תגמולים"),
                            item.get("סך_תגמולים"),
                        ]
                        edu_amount = 0.0
                        for raw in candidate_vals:
                            try:
                                edu_amount = float(raw or 0)
                            except (TypeError, ValueError):
                                edu_amount = 0.0
                            if edu_amount > 0:
                                break
                        if edu_amount > 0:
                            item["קרן_השתלמות"] = edu_amount
                normalized.append(item)
            return normalized, snapshot_at

    return None


def load_latest_pension_portfolio_snapshot_models(
    db: Session,
    client_id: int,
    *,
    lookback_scenarios: int = 20,
) -> tuple[list[PensionPortfolioAccount], str] | None:
    raw = load_latest_pension_portfolio_snapshot(
        db,
        client_id,
        lookback_scenarios=lookback_scenarios,
    )
    if raw is None:
        return None

    portfolio, snapshot_at = raw
    models: list[PensionPortfolioAccount] = []
    for item in portfolio:
        if not isinstance(item, dict):
            continue
        try:
            models.append(PensionPortfolioAccount.model_validate(item))
        except Exception:
            continue

    return models, snapshot_at


def load_current_effective_state(
    db: Session,
    client_id: int,
) -> dict[str, Any]:
    snapshot = (
        db.query(Scenario)
        .filter(Scenario.client_id == client_id)
        .filter(Scenario.scenario_name == "pension_portfolio_snapshot")
        .order_by(Scenario.created_at.desc())
        .first()
    )

    snapshot_id = getattr(snapshot, "id", None) if snapshot is not None else None
    snapshot_at = ""
    snapshot_portfolio_count = None
    last_operation_type = None
    last_trace_id = None
    if snapshot is not None:
        try:
            snapshot_at = snapshot.created_at.isoformat()
        except Exception:
            snapshot_at = ""
        try:
            params = json.loads(snapshot.parameters) if snapshot.parameters else {}
        except Exception:
            params = {}
        portfolio = params.get("pension_portfolio")
        if isinstance(portfolio, list):
            snapshot_portfolio_count = len(portfolio)
        meta = params.get("_meta") if isinstance(params, dict) else None
        if isinstance(meta, dict):
            last_operation_type = meta.get("operation_type")
            last_trace_id = meta.get("trace_id")

    try:
        pension_funds_count = int(
            db.query(PensionFund).filter(PensionFund.client_id == client_id).count()
        )
    except Exception:
        pension_funds_count = 0
    try:
        capital_assets_count = int(
            db.query(CapitalAsset).filter(CapitalAsset.client_id == client_id).count()
        )
    except Exception:
        capital_assets_count = 0

    is_recent_update = False
    if snapshot is not None:
        try:
            created_at = snapshot.created_at
            if created_at is not None:
                now = datetime.now(timezone.utc)
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                is_recent_update = (now - created_at).total_seconds() <= 300
        except Exception:
            is_recent_update = False

    return {
        "snapshot_id": snapshot_id,
        "snapshot_at": snapshot_at,
        "snapshot_portfolio_count": snapshot_portfolio_count,
        "pension_funds_count": pension_funds_count,
        "capital_assets_count": capital_assets_count,
        "last_operation_type": last_operation_type,
        "last_trace_id": last_trace_id,
        "recent_update": bool(is_recent_update),
    }
