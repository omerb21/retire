import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.scenario import Scenario
from app.services.llm_chat.intent_classifier import ChatIntent


def _parse_iso_datetime_utc(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    cleaned = raw.strip()
    try:
        if cleaned.endswith("Z"):
            cleaned = cleaned[:-1] + "+00:00"
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _load_latest_snapshot_meta(
    *, db: Session, client_id: int | None
) -> dict[str, Any] | None:
    if client_id is None:
        return None
    latest = (
        db.query(Scenario)
        .filter(Scenario.client_id == client_id)
        .filter(Scenario.scenario_name == "pension_portfolio_snapshot")
        .order_by(Scenario.created_at.desc(), Scenario.id.desc())
        .first()
    )
    if latest is None:
        return None
    try:
        params = json.loads(latest.parameters) if latest.parameters else {}
    except Exception:
        params = {}
    if not isinstance(params, dict):
        return None
    meta = params.get("_meta")
    return meta if isinstance(meta, dict) else None


def _build_restore_snapshot_banner(
    *,
    db: Session,
    client_id: int | None,
    effective_state: dict | None,
    now_utc: datetime,
) -> str | None:
    if client_id is None:
        return None
    if not isinstance(effective_state, dict):
        return None

    meta = _load_latest_snapshot_meta(db=db, client_id=client_id)
    if not isinstance(meta, dict):
        return None
    op_type = str(meta.get("operation_type") or "").strip()
    if op_type != "restore_snapshot":
        return None
    restored_at = _parse_iso_datetime_utc(meta.get("restored_at_utc"))
    if restored_at is None:
        return None

    try:
        age_sec = (now_utc - restored_at).total_seconds()
    except Exception:
        return None
    if age_sec < 0 or age_sec > 120:
        return None
    return "מצב מערכת: שוחזר סנאפסוט (restore_snapshot). אפשר להמשיך לתכנית/תרחיש."


def _latest_snapshot_operation_type(
    *, db: Session, client_id: int | None
) -> str | None:
    if client_id is None:
        return None
    meta = _load_latest_snapshot_meta(db=db, client_id=client_id)
    if not isinstance(meta, dict):
        return None
    op_type = str(meta.get("operation_type") or "").strip()
    return op_type if op_type else None


def _wrap_with_restore_banner(
    *,
    inner,
    db: Session,
    client_id: int | None,
    effective_state: dict | None,
    resolved_intent,
):
    now = datetime.now(timezone.utc)
    banner = _build_restore_snapshot_banner(
        db=db,
        client_id=client_id,
        effective_state=effective_state,
        now_utc=now,
    )
    if (
        isinstance(banner, str)
        and banner.strip()
        and (resolved_intent != ChatIntent.REPORT)
    ):
        yield banner.strip() + "\n\n"
    yield from inner


def _build_recent_state_banner(
    *,
    db: Session,
    client_id: int | None,
    effective_state: dict | None,
    resolved_intent,
) -> str | None:
    now = datetime.now(timezone.utc)
    restore_banner = _build_restore_snapshot_banner(
        db=db,
        client_id=client_id,
        effective_state=effective_state,
        now_utc=now,
    )
    if isinstance(restore_banner, str) and restore_banner.strip():
        return restore_banner

    if not isinstance(effective_state, dict):
        return None
    if not bool(effective_state.get("recent_update")):
        return None
    op_type = str(effective_state.get("last_operation_type") or "").strip()
    if op_type:
        return f"מצב מערכת: עודכן לאחר פעולה אחרונה ({op_type})"
    return "מצב מערכת: עודכן לאחר פעולה אחרונה"
