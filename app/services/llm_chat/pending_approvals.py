import hashlib
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import Scenario


_PENDING_APPROVAL_SCENARIO_NAME = "pending_approval"
_DEFAULT_TTL_SECONDS = 15 * 60


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _stable_json(obj) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except Exception:
        return "{}"


def compute_intent_key(
    *,
    client_id: int,
    tool_name: str,
    request_kind: str,
    tool_args: dict,
) -> str:
    raw = f"{client_id}|{request_kind}|{tool_name}|{_stable_json(tool_args)}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def store_pending_approval_ui_action(
    *,
    db: Session,
    client_id: int,
    request_kind: str,
    tool_name: str,
    tool_args: dict,
    ui_action: str,
    trace_id: str | None = None,
    ttl_seconds: int = _DEFAULT_TTL_SECONDS,
) -> bool:
    if client_id is None:
        return False
    if not isinstance(tool_name, str) or not tool_name.strip():
        return False
    if not isinstance(request_kind, str) or not request_kind.strip():
        return False
    if not isinstance(tool_args, dict):
        tool_args = {}
    if not isinstance(ui_action, str) or not ui_action.strip():
        return False

    now = _utcnow()
    expires_at = now + timedelta(seconds=int(ttl_seconds or _DEFAULT_TTL_SECONDS))
    intent_key = compute_intent_key(
        client_id=int(client_id),
        tool_name=tool_name,
        request_kind=request_kind,
        tool_args=tool_args,
    )

    try:
        db.query(Scenario).filter(Scenario.client_id == client_id).filter(
            Scenario.scenario_name == _PENDING_APPROVAL_SCENARIO_NAME
        ).delete(synchronize_session=False)
        db.flush()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return False

    payload = {
        "version": 2,
        "intent_key": intent_key,
        "request_kind": request_kind,
        "tool_name": tool_name,
        "arguments": tool_args,
        "ui_action": ui_action,
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
    }
    if trace_id:
        payload["trace_id"] = trace_id

    try:
        scenario = Scenario(
            client_id=client_id,
            scenario_name=_PENDING_APPROVAL_SCENARIO_NAME,
            apply_tax_planning=False,
            apply_capitalization=False,
            apply_exemption_shield=False,
            parameters=json.dumps(payload, ensure_ascii=False),
        )
        db.add(scenario)
        db.flush()
        db.commit()
        return True
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return False


def load_pending_approval_ui_action_if_match(
    *,
    db: Session,
    client_id: int,
    request_kind: str,
    tool_name: str,
) -> str | None:
    if client_id is None:
        return None
    if not isinstance(request_kind, str) or not request_kind.strip():
        return None
    if not isinstance(tool_name, str) or not tool_name.strip():
        return None

    try:
        row = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == _PENDING_APPROVAL_SCENARIO_NAME)
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

    if str(parsed.get("tool_name") or "").strip() != tool_name:
        return None
    if str(parsed.get("request_kind") or "").strip() != request_kind:
        return None

    expires_raw = parsed.get("expires_at")
    if isinstance(expires_raw, str) and expires_raw.strip():
        try:
            expires_at = datetime.fromisoformat(expires_raw.strip())
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if _utcnow() >= expires_at:
                return None
        except Exception:
            return None

    ui_action = parsed.get("ui_action")
    if not isinstance(ui_action, str) or not ui_action.strip():
        return None
    return ui_action
