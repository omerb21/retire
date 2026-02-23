from __future__ import annotations

import os
import re
from typing import Any


_REDACTION_FAILED_STR = "[REDACTION_FAILED]"
_REDACTED_STR = "[REDACTED]"

_EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)


def _enabled() -> bool:
    try:
        return (os.getenv("TRACE_PII_REDACTION_ENABLED") or "1").strip() != "0"
    except Exception:
        return True


def _placeholder_for(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {"redaction_failed": True}
    if isinstance(obj, (list, tuple)):
        return [_REDACTION_FAILED_STR]
    if isinstance(obj, str):
        return _REDACTION_FAILED_STR
    return {"redaction_failed": True}


def _redact_email_in_string(s: str) -> str:
    try:
        if "@" not in (s or ""):
            return s or ""
        return _EMAIL_RE.sub(_REDACTED_STR, s or "")
    except Exception:
        return _REDACTION_FAILED_STR


def _key_suggests_redact(key: str) -> bool:
    k = (key or "").casefold()
    if not k:
        return False

    safe_id_keys = {
        "path_id",
        "tool_id",
        "capability_id",
        "trace_id",
        "request_id",
        "session_id",
        "client_id",
    }
    if k in safe_id_keys:
        return False

    if k in {
        "id",
        "id_number",
        "identity_number",
        "national_id",
        "tz",
        "תז",
        "זהות",
    }:
        return True

    if k.endswith("_id"):
        return True

    hints = (
        "email",
        "e-mail",
        "mail",
        "phone",
        "mobile",
        "cell",
        "tel",
        "טלפון",
        "נייד",
        "account",
        "iban",
        "bank",
        "חשבון",
        "סניף",
        "address",
        "street",
        "city",
        "zip",
        "house",
        "רחוב",
        "עיר",
        "מיקוד",
        "דירה",
        "בית",
    )
    return any(h in k for h in hints)


def redact_payload(payload: Any) -> Any:
    if not _enabled():
        return payload

    try:
        if payload is None:
            return None

        if isinstance(payload, (bool, int, float)):
            return payload

        if isinstance(payload, str):
            return _redact_email_in_string(payload)

        if isinstance(payload, dict):
            out: dict[str, Any] = {}
            for k, v in payload.items():
                ks = str(k)
                if _key_suggests_redact(ks):
                    out[ks] = _REDACTED_STR
                else:
                    out[ks] = redact_payload(v)
            return out

        if isinstance(payload, (list, tuple)):
            return [redact_payload(x) for x in payload]

        return _placeholder_for(payload)

    except Exception:
        return _placeholder_for(payload)
