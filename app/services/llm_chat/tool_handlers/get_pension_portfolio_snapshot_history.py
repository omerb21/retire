import json
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.scenario import Scenario


def _safe_float(val: Any) -> float:
    try:
        if val is None:
            return 0.0
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            cleaned = val.replace(",", "").replace("₪", "").strip()
            if not cleaned:
                return 0.0
            return float(cleaned)
        return float(val)
    except Exception:
        return 0.0


def _estimate_nonzero_balance_rows(portfolio: Any) -> int:
    if not isinstance(portfolio, list):
        return 0

    candidates = (
        "יתרה",
        "balance",
        "סך_תגמולים",
        "תגמולים",
        "צבירה",
        "current_balance",
        "amount",
    )

    count = 0
    for row in portfolio:
        if not isinstance(row, dict):
            continue
        raw = None
        for key in candidates:
            if key in row:
                raw = row.get(key)
                break
        if raw is None:
            continue
        if _safe_float(raw) > 0.01:
            count += 1
    return count


def handle_get_pension_portfolio_snapshot_history(*, args: dict, client_id: int, db: Session) -> str:
    rows = (
        db.query(Scenario)
        .filter(Scenario.client_id == client_id)
        .filter(Scenario.scenario_name == "pension_portfolio_snapshot")
        .order_by(Scenario.created_at.desc())
        .limit(10)
        .all()
    )

    out: list[dict[str, Any]] = []
    for row in rows:
        params = {}
        try:
            params = json.loads(row.parameters) if row.parameters else {}
        except Exception:
            params = {}

        meta = params.get("_meta") if isinstance(params, dict) else None
        op_type = None
        if isinstance(meta, dict):
            op_type = meta.get("operation_type")

        portfolio = params.get("pension_portfolio") if isinstance(params, dict) else None
        est_nonzero = _estimate_nonzero_balance_rows(portfolio)

        created_at = None
        try:
            created_at = row.created_at.isoformat() if isinstance(row.created_at, datetime) else None
        except Exception:
            created_at = None

        out.append(
            {
                "scenario_id": int(getattr(row, "id", 0) or 0),
                "created_at": created_at or "",
                "meta": {"operation_type": str(op_type) if op_type is not None else ""},
                "estimated_nonzero_balance_rows": int(est_nonzero),
            }
        )

    return json.dumps(out, ensure_ascii=False)
