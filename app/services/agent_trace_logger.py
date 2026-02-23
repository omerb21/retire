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

from app.utils.trace_context import generate_trace_id, get_current_trace_id, set_current_trace_id

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
        effective_trace_id = trace_id or get_current_trace_id() or generate_trace_id()
        _ = (payload_text, session_id)

        prev_trace_id: Optional[str] = None
        try:
            prev_trace_id = get_current_trace_id()
        except Exception:
            prev_trace_id = None

        try:
            if effective_trace_id and effective_trace_id != prev_trace_id:
                set_current_trace_id(effective_trace_id)

            from app.services.agent_eyes.event_collector import emit_event

            emit_event(event_type=event_type, payload=payload, client_id=client_id, endpoint=endpoint)
        finally:
            try:
                if prev_trace_id and prev_trace_id != effective_trace_id:
                    set_current_trace_id(prev_trace_id)
            except Exception:
                pass

    except Exception as exc:
        # Never crash the caller
        logger.warning("agent_trace_logger failed to persist event: %s", exc)


def emit_trace_error(
    *,
    exc: BaseException,
    where: str = "",
    client_id: Optional[int] = None,
    endpoint: Optional[str] = None,
) -> None:
    """Persist a standardised ``error`` event.  Never raises."""
    import traceback as _tb_mod

    try:
        tb_preview = _tb_mod.format_exc()
        if tb_preview == "NoneType: None\n" or not tb_preview.strip():
            tb_preview = "".join(_tb_mod.format_exception(type(exc), exc, exc.__traceback__))
        log_trace_event(
            event_type="error",
            payload={
                "error_type": type(exc).__name__,
                "message": str(exc)[:2000],
                "where": where,
                "traceback_preview": tb_preview[:800],
            },
            client_id=client_id,
            endpoint=endpoint,
        )
    except Exception:
        pass
