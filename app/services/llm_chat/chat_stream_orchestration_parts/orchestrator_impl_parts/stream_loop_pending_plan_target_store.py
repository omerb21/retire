import json
from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session

from app.models.scenario import Scenario


def _store_pending_plan_target(
    *,
    db: Session,
    client_id: int,
    ttl_seconds: int,
    infer_pending_retirement_fields_for_marker,
) -> None:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=ttl_seconds)
    pending_age, pending_date = infer_pending_retirement_fields_for_marker(client_id=client_id)
    payload = {
        "kind": "pending_plan_target",
        "active": True,
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
    }
    if pending_age is not None:
        payload["pending_retirement_age"] = int(pending_age)
    if isinstance(pending_date, str) and pending_date.strip():
        payload["pending_retirement_date"] = pending_date.strip()

    try:
        (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "pending_plan_target")
            .delete(synchronize_session=False)
        )
        db.flush()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return

    try:
        scenario = Scenario(
            client_id=client_id,
            scenario_name="pending_plan_target",
            apply_tax_planning=False,
            apply_capitalization=False,
            apply_exemption_shield=False,
            parameters=json.dumps(payload, ensure_ascii=False),
        )
        db.add(scenario)
        db.flush()
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass


def _clear_pending_plan_target(*, db: Session, client_id: int) -> None:
    try:
        (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "pending_plan_target")
            .delete(synchronize_session=False)
        )
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass


def _load_pending_plan_target(*, db: Session, client_id: int) -> dict | None:
    try:
        row = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "pending_plan_target")
            .order_by(Scenario.created_at.desc())
            .first()
        )
    except Exception:
        row = None
    if row is None or not getattr(row, "parameters", None):
        return None
    try:
        parsed = json.loads(row.parameters)
    except Exception:
        return None
    if not isinstance(parsed, dict):
        return None

    if parsed.get("active", True) is False:
        return None

    expires_raw = parsed.get("expires_at")
    expired = False
    if isinstance(expires_raw, str) and expires_raw.strip():
        try:
            expires_at = datetime.fromisoformat(expires_raw.strip())
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            expired = datetime.now(timezone.utc) >= expires_at
        except Exception:
            expired = False

    if str(parsed.get("kind") or "").strip() != "pending_plan_target":
        return None
    if expired:
        parsed = dict(parsed)
        parsed["_expired"] = True
    return parsed
