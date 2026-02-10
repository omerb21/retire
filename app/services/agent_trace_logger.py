"""
Agent Trace Logger – safe helper to persist AgentTraceEvent rows.

Usage from anywhere:
    from app.services.agent_trace_logger import log_trace_event
    log_trace_event(
        trace_id="...",
        event_type="tool_call",
        payload={"name": "BUILD_TARGET_PENSION_PLAN", ...},
        client_id=42,
        endpoint="/api/v1/llm/pension-chat",
    )

Safe: never raises, never crashes the request.  On failure it logs and moves on.
"""
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional

from app.database import SessionLocal
from app.utils.trace_context import get_current_trace_id

logger = logging.getLogger("app.agent_trace")

MAX_PAYLOAD_SIZE = 500_000  # ~500 KB; truncate beyond this


def _safe_json(obj: Any) -> tuple[str, bool, int]:
    """Serialize *obj* to a JSON string, truncating if needed.

    Returns ``(json_str, is_truncated, original_byte_size)``.
    """
    try:
        raw = json.dumps(obj, ensure_ascii=False, default=str)
    except Exception:
        raw = json.dumps({"_serialization_error": True, "repr": repr(obj)[:2000]})

    original_size = len(raw)

    if original_size > MAX_PAYLOAD_SIZE:
        truncated = {
            "truncated": True,
            "original_size": original_size,
            "preview": raw[:MAX_PAYLOAD_SIZE // 2],
        }
        return json.dumps(truncated, ensure_ascii=False), True, original_size
    return raw, False, original_size


def log_trace_event(
    *,
    trace_id: Optional[str] = None,
    event_type: str,
    payload: Any = None,
    payload_text: Optional[str] = None,
    client_id: Optional[int] = None,
    endpoint: Optional[str] = None,
    session_id: Optional[str] = None,
) -> None:
    """Persist one event row.  Fire-and-forget – never raises."""
    try:
        from app.models.agent_trace_event import AgentTraceEvent

        effective_trace_id = trace_id or get_current_trace_id() or "unknown"

        payload_json_str: Optional[str] = None
        truncated = False
        original_size: Optional[int] = None
        if payload is not None:
            payload_json_str, truncated, original_size = _safe_json(payload)

        db = SessionLocal()
        try:
            event = AgentTraceEvent(
                trace_id=effective_trace_id,
                session_id=session_id,
                client_id=client_id,
                endpoint=endpoint,
                event_type=event_type,
                payload_json=payload_json_str,
                payload_text=payload_text,
                is_truncated=truncated,
                payload_size=original_size,
                created_at=datetime.now(timezone.utc),
            )
            db.add(event)
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
        # Never crash the caller
        logger.warning("agent_trace_logger failed to persist event: %s", exc)
