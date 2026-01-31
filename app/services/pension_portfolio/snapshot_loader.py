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


def dedupe_pension_portfolio_snapshot(db: Session, client_id: int) -> tuple[int | None, list[int]]:
    snapshots = (
        db.query(Scenario)
        .filter(Scenario.client_id == client_id)
        .filter(Scenario.scenario_name == "pension_portfolio_snapshot")
        .order_by(Scenario.id.desc())
        .all()
    )

    if not snapshots:
        return None, []

    keep = snapshots[0]
    keep_id = int(getattr(keep, "id", 0) or 0) or None

    deleted_ids: list[int] = []
    if len(snapshots) > 1:
        deleted_ids = [int(getattr(s, "id", 0) or 0) for s in snapshots[1:]]
        deleted_ids = [sid for sid in deleted_ids if sid and (keep_id is None or sid != keep_id)]
        if deleted_ids:
            db.query(Scenario).filter(Scenario.id.in_(deleted_ids)).delete(
                synchronize_session=False
            )

    db.commit()
    return keep_id, deleted_ids


def load_latest_pension_portfolio_snapshot(
    db: Session,
    client_id: int,
    *,
    lookback_scenarios: int = 20,
) -> tuple[list[dict[str, Any]], str] | None:
    def _safe_float(value: Any) -> float:
        try:
            if value is None:
                return 0.0
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                cleaned = value.replace(",", "").replace("₪", "").strip()
                if not cleaned:
                    return 0.0
                return float(cleaned)
            return float(value)
        except Exception:
            return 0.0

    def _portfolio_has_value(portfolio: Any) -> bool:
        if not isinstance(portfolio, list) or not portfolio:
            return False
        component_prefixes = ("תגמולי_", "פיצויים_")
        for acc in portfolio:
            if not isinstance(acc, dict):
                continue
            if _safe_float(acc.get("יתרה") or acc.get("balance") or acc.get("current_balance")) > 0.01:
                return True
            if _safe_float(acc.get("סך_רכיבים") or acc.get("total_components")) > 0.01:
                return True
            if _safe_float(acc.get("סך_תגמולים") or acc.get("תגמולים") or acc.get("total_contributions")) > 0.01:
                return True
            if _safe_float(acc.get("קרן_השתלמות") or acc.get("education_fund")) > 0.01:
                return True
            for k, v in acc.items():
                if isinstance(k, str) and k.startswith(component_prefixes) and _safe_float(v) > 0.01:
                    return True
        return False

    scenarios = (
        db.query(Scenario)
        .filter(Scenario.client_id == client_id)
        .filter(Scenario.scenario_name == "pension_portfolio_snapshot")
        .order_by(Scenario.created_at.desc())
        .limit(int(lookback_scenarios))
        .all()
    )

    chosen: tuple[list[dict[str, Any]], str, str] | None = None
    chosen_any: tuple[list[dict[str, Any]], str, str] | None = None

    for scenario in scenarios:
        if not scenario.parameters:
            continue
        try:
            params = json.loads(scenario.parameters)
        except Exception:
            continue
        portfolio = params.get("pension_portfolio")
        if not (isinstance(portfolio, list) and portfolio):
            continue
        if not _portfolio_has_value(portfolio):
            continue

        snapshot_at = ""
        try:
            snapshot_at = scenario.created_at.isoformat()
        except Exception:
            snapshot_at = ""

        meta = params.get("_meta") if isinstance(params, dict) else None
        op_type = None
        if isinstance(meta, dict):
            op_type = str(meta.get("operation_type") or "").strip()

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

        if chosen_any is None:
            chosen_any = (normalized, snapshot_at, op_type or "")
        if op_type != "TRANSFORM_FUNDS_TO_ASSETS":
            chosen = (normalized, snapshot_at, op_type or "")
            break

    if chosen is None:
        chosen = chosen_any

    if chosen is not None:
        return chosen[0], chosen[1]

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
