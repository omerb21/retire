"""
Agent Eyes – in-memory + DB event collector (Stage 2 + Stage 3).

Captures structured events with full payloads into:
  1. A per-process ring buffer (collections.deque, maxlen=2000)
  2. A dedicated JSONL logger (``agent_eyes``) for durable evidence
  3. The ``agent_trace_event`` DB table (dual-write, best-effort)

Every event carries the current ``trace_id`` from the existing
TraceIdMiddleware context-var so that all events within a single
request can be correlated.

Public API
----------
    emit_event(event_type, payload, *, client_id=None, endpoint=None)
    get_events_by_trace(trace_id) -> list[dict]
    get_recent_events(n=50) -> list[dict]
    clear_buffer()                         # for tests only
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections import deque
from contextvars import ContextVar
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Optional

from app.utils.trace_context import generate_trace_id, get_current_trace_id

_log = logging.getLogger("agent_eyes")

_in_db_persist: ContextVar[bool] = ContextVar("agent_eyes_in_db_persist", default=False)

# ---------------------------------------------------------------------------
# Truncation
# ---------------------------------------------------------------------------
_MAX_PAYLOAD_CHARS = 200_000  # ~200 KB per event payload (in-memory)
_MAX_DB_PAYLOAD_BYTES = 128_000  # 128 KB hard limit for DB column


def _truncate(obj: Any) -> Any:
    """Recursively truncate large string values and mark them."""
    if isinstance(obj, str):
        if len(obj) > _MAX_PAYLOAD_CHARS:
            return {
                "_truncated": True,
                "_original_len": len(obj),
                "data": obj[:_MAX_PAYLOAD_CHARS],
            }
        return obj
    if isinstance(obj, dict):
        return {k: _truncate(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_truncate(x) for x in obj]
    if isinstance(obj, BaseException):
        return str(obj)
    return obj


def _safe_json_for_db(payload: Any) -> tuple[str, bool, int]:
    """Serialize *payload* to a JSON string suitable for DB storage.

    Returns ``(json_str, is_truncated, original_byte_len)``.
    If the serialized form exceeds ``_MAX_DB_PAYLOAD_BYTES`` the value
    is replaced with a truncated summary carrying ``_truncated: true``.
    """
    try:
        raw = json.dumps(payload, ensure_ascii=False, default=str)
    except Exception:
        raw = json.dumps({"_serialization_error": True, "repr": repr(payload)[:2000]})

    original_len = len(raw.encode("utf-8", errors="replace"))

    if original_len > _MAX_DB_PAYLOAD_BYTES:
        truncated_obj = {
            "_truncated": True,
            "_original_len": original_len,
            "data": raw[: _MAX_DB_PAYLOAD_BYTES // 2],
        }
        return json.dumps(truncated_obj, ensure_ascii=False), True, original_len

    return raw, False, original_len


# ---------------------------------------------------------------------------
# Ring buffer
# ---------------------------------------------------------------------------
_BUFFER_MAX = 2000
_buffer: deque[dict] = deque(maxlen=_BUFFER_MAX)
_lock = Lock()


# ---------------------------------------------------------------------------
# DB persistence (best-effort, never raises)
# ---------------------------------------------------------------------------
# Allow tests to inject a custom SessionLocal so that DB writes go to the
# test database instead of the production one.
_session_factory_override: Any = None


def _persist_to_db(
    trace_id: str,
    event_type: str,
    created_at_dt: datetime,
    payload: Any,
    client_id: int | None,
    endpoint: str | None,
) -> None:
    """Best-effort write to agent_trace_event table.  Never raises."""
    try:
        from app.models.agent_trace_event import AgentTraceEvent

        try:
            redaction_enabled = (
                os.getenv("TRACE_PII_REDACTION_ENABLED") or "1"
            ).strip() != "0"
        except Exception:
            redaction_enabled = True

        if redaction_enabled:
            try:
                from app.services.observability.pii_redactor import redact_payload

                redacted_payload = redact_payload(payload)

                redaction_failed = False
                try:
                    redaction_failed = bool(
                        redacted_payload == {"redaction_failed": True}
                        or redacted_payload == "[REDACTION_FAILED]"
                        or redacted_payload == ["[REDACTION_FAILED]"]
                    )
                except Exception:
                    redaction_failed = True

                if redaction_failed:
                    token = _in_db_persist.set(True)
                    try:
                        from app.services.agent_trace_logger import log_trace_event

                        log_trace_event(
                            trace_id=trace_id,
                            event_type="pii_redaction_failed",
                            payload={
                                "payload_type": type(payload).__name__,
                                "reason": "exception",
                            },
                            client_id=client_id,
                            endpoint=endpoint,
                        )
                    except Exception:
                        pass
                    finally:
                        try:
                            _in_db_persist.reset(token)
                        except Exception:
                            pass

                payload = redacted_payload
            except Exception:
                payload = {"redaction_failed": True}

        session_factory = _session_factory_override
        if session_factory is None:
            from app.database import SessionLocal

            session_factory = SessionLocal

        payload_json_str: str | None = None
        is_truncated = False
        payload_size: int | None = None

        if payload is not None:
            payload_json_str, is_truncated, payload_size = _safe_json_for_db(payload)

        db = session_factory()
        try:
            row = AgentTraceEvent(
                trace_id=trace_id,
                client_id=client_id,
                endpoint=endpoint,
                event_type=event_type,
                payload_json=payload_json_str,
                is_truncated=is_truncated,
                payload_size=payload_size,
                created_at=created_at_dt,
            )
            db.add(row)
            db.commit()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
            raise
        finally:
            try:
                db.close()
            except Exception:
                pass

    except Exception as exc:
        try:
            _log.debug("DB persist failed (non-fatal): %s", exc)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def emit_event(
    event_type: str,
    payload: Any = None,
    *,
    client_id: int | None = None,
    endpoint: str | None = None,
) -> None:
    """Record one event.  Never raises – safe to call from anywhere."""
    try:
        trace_id = get_current_trace_id() or generate_trace_id()
        created_at_dt = datetime.now(timezone.utc)
        created_at = created_at_dt.isoformat()
        ts_mono = time.monotonic()

        safe_payload = _truncate(payload) if payload is not None else None

        event: dict[str, Any] = {
            "trace_id": trace_id,
            "event_type": event_type,
            "created_at": created_at,
            "ts_mono": ts_mono,
            "client_id": client_id,
            "endpoint": endpoint,
            "payload": safe_payload,
        }

        # 1) ring buffer
        with _lock:
            _buffer.append(event)

        # 2) JSONL log line
        try:
            _log.info(json.dumps(event, ensure_ascii=False, default=str))
        except Exception:
            _log.info(
                json.dumps(
                    {
                        "event_type": event_type,
                        "trace_id": trace_id,
                        "error": "serialization_failed",
                    }
                )
            )

        # 3) DB persistence (best-effort)
        try:
            if not _in_db_persist.get():
                _persist_to_db(
                    trace_id=trace_id,
                    event_type=event_type,
                    created_at_dt=created_at_dt,
                    payload=payload,
                    client_id=client_id,
                    endpoint=endpoint,
                )
        except Exception:
            pass

    except Exception as exc:
        # Absolute last resort – never crash the caller
        try:
            _log.warning("emit_event failed: %s", exc)
        except Exception:
            pass


def get_events_by_trace(trace_id: str) -> list[dict]:
    """Return all buffered events for *trace_id*, oldest first."""
    with _lock:
        return [e for e in _buffer if e.get("trace_id") == trace_id]


def get_recent_events(n: int = 50) -> list[dict]:
    """Return the *n* most recent events from the buffer."""
    with _lock:
        items = list(_buffer)
    return items[-n:]


def clear_buffer() -> None:
    """Clear the ring buffer.  Intended for test isolation only."""
    with _lock:
        _buffer.clear()


def delete_trace_events_older_than(
    *, cutoff_dt: datetime, dry_run: bool = False
) -> int:
    """Delete trace events with created_at < cutoff_dt.

    Returns the number of rows deleted (or that would be deleted in dry-run).
    """
    try:
        from app.models.agent_trace_event import AgentTraceEvent

        session_factory = _session_factory_override
        if session_factory is None:
            from app.database import SessionLocal

            session_factory = SessionLocal

        db = session_factory()
        try:
            q = db.query(AgentTraceEvent).filter(AgentTraceEvent.created_at < cutoff_dt)
            count = int(q.count())
            if dry_run:
                return count

            deleted = int(q.delete(synchronize_session=False))
            db.commit()
            return deleted
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
            raise
        finally:
            try:
                db.close()
            except Exception:
                pass
    except Exception:
        return 0
