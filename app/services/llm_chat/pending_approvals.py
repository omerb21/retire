import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import re

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


_NUMERIC_STRING_RE = re.compile(r"^[+-]?(?:\d+)(?:\.\d+)?$")


def _decimal_to_canonical_str(value: Decimal) -> str:
    try:
        normalized = value.normalize()
    except Exception:
        normalized = value
    try:
        rendered = format(normalized, "f")
    except Exception:
        rendered = str(normalized)
    return rendered


def _should_convert_numeric_string(raw: str) -> bool:
    s = raw.strip()
    if not s:
        return False
    if not _NUMERIC_STRING_RE.match(s):
        return False
    body = s
    if body[0] in ("+", "-"):
        body = body[1:]
        if not body:
            return False
    if "." not in body and len(body) > 1 and body.startswith("0"):
        return False
    return True


def canonicalize_args(obj):
    if obj is None:
        return None
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, (int, float, Decimal)):
        try:
            as_decimal = Decimal(str(obj))
        except Exception:
            return str(obj)
        return _decimal_to_canonical_str(as_decimal)
    if isinstance(obj, str):
        if not _should_convert_numeric_string(obj):
            return obj
        try:
            as_decimal = Decimal(obj.strip())
        except InvalidOperation:
            return obj
        except Exception:
            return obj
        return _decimal_to_canonical_str(as_decimal)
    if isinstance(obj, dict):
        out = {}
        for k in sorted(obj.keys(), key=lambda x: str(x)):
            out[k] = canonicalize_args(obj.get(k))
        return out
    if isinstance(obj, (list, tuple)):
        return [canonicalize_args(v) for v in obj]
    return str(obj)


def compute_args_hash(tool_args: dict) -> str:
    if not isinstance(tool_args, dict):
        tool_args = {}
    try:
        canonicalized = canonicalize_args(tool_args)
        raw_json = json.dumps(
            canonicalized,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except Exception:
        raw_json = "{}"
    raw = raw_json.encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


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
    args_hash = compute_args_hash(tool_args)

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
        "args_hash": args_hash,
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

    parsed = load_pending_approval_payload_if_match(
        db=db,
        client_id=client_id,
        request_kind=request_kind,
        tool_name=tool_name,
    )
    if parsed is None:
        return None
    ui_action = parsed.get("ui_action")
    if not isinstance(ui_action, str) or not ui_action.strip():
        return None
    return ui_action


def load_pending_approval_payload_if_match(
    *,
    db: Session,
    client_id: int,
    request_kind: str,
    tool_name: str,
) -> dict | None:
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

    return parsed


def load_pending_approval_payload_if_match_and_args_hash(
    *,
    db: Session,
    client_id: int,
    request_kind: str,
    tool_name: str,
    args_hash: str,
) -> dict | None:
    if not isinstance(args_hash, str) or not args_hash.strip():
        return None
    parsed = load_pending_approval_payload_if_match(
        db=db,
        client_id=client_id,
        request_kind=request_kind,
        tool_name=tool_name,
    )
    if parsed is None:
        return None
    stored = parsed.get("args_hash")
    if not isinstance(stored, str) or not stored.strip():
        return None
    if stored.strip() != args_hash.strip():
        return None
    return parsed
