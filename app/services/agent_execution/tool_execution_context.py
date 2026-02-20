from __future__ import annotations

from contextvars import ContextVar
import threading
import time

from app.schemas.llm_chat import ChatRequest
from app.services.agent_execution.policy import PolicyDecision
from app.services.intent_classifier import IntentType


_current_request: ContextVar[ChatRequest | None] = ContextVar("tool_exec_request", default=None)
_current_policy_decision: ContextVar[PolicyDecision | None] = ContextVar("tool_exec_policy_decision", default=None)
_current_intent_type: ContextVar[IntentType | None] = ContextVar("tool_exec_intent_type", default=None)
_current_streaming: ContextVar[bool] = ContextVar("tool_exec_streaming", default=False)
_tool_ok_seen: ContextVar[bool] = ContextVar("tool_ok_seen", default=False)

_TOOL_OK_TRACE_TTL_SEC = 3600.0
_tool_ok_seen_by_trace: dict[str, float] = {}
_tool_ok_lock = threading.Lock()


def _get_current_trace_id_safe() -> str | None:
    try:
        from app.utils.trace_context import get_current_trace_id

        trace_id = get_current_trace_id()
        if isinstance(trace_id, str) and trace_id.strip():
            return trace_id.strip()
    except Exception:
        return None
    return None


def _prune_tool_ok_seen_by_trace(now: float) -> None:
    if not _tool_ok_seen_by_trace:
        return
    cutoff = now - _TOOL_OK_TRACE_TTL_SEC
    stale: list[str] = []
    for tid, ts in _tool_ok_seen_by_trace.items():
        if ts < cutoff:
            stale.append(tid)
    for tid in stale:
        _tool_ok_seen_by_trace.pop(tid, None)


def set_tool_execution_context(
    *,
    request: ChatRequest | None,
    policy_decision: PolicyDecision | None,
    intent_type: IntentType | None,
    streaming: bool,
) -> None:
    _current_request.set(request)
    _current_policy_decision.set(policy_decision)
    _current_intent_type.set(intent_type)
    _current_streaming.set(bool(streaming))


def get_current_tool_execution_request() -> ChatRequest | None:
    return _current_request.get()


def get_current_tool_execution_policy_decision() -> PolicyDecision | None:
    return _current_policy_decision.get()


def get_current_tool_execution_intent_type() -> IntentType | None:
    return _current_intent_type.get()


def get_current_tool_execution_streaming() -> bool:
    return bool(_current_streaming.get())


def reset_tool_ok_seen() -> None:
    _tool_ok_seen.set(False)

    trace_id = _get_current_trace_id_safe()
    if trace_id:
        try:
            now = time.monotonic()
            with _tool_ok_lock:
                _tool_ok_seen_by_trace.pop(trace_id, None)
                if len(_tool_ok_seen_by_trace) > 1000:
                    _prune_tool_ok_seen_by_trace(now)
        except Exception:
            pass


def mark_tool_ok_seen() -> None:
    _tool_ok_seen.set(True)

    trace_id = _get_current_trace_id_safe()
    if trace_id:
        try:
            now = time.monotonic()
            with _tool_ok_lock:
                _tool_ok_seen_by_trace[trace_id] = now
                if len(_tool_ok_seen_by_trace) > 1000:
                    _prune_tool_ok_seen_by_trace(now)
        except Exception:
            pass


def get_tool_ok_seen() -> bool:
    if bool(_tool_ok_seen.get()):
        return True

    trace_id = _get_current_trace_id_safe()
    if not trace_id:
        return False

    try:
        now = time.monotonic()
        with _tool_ok_lock:
            ts = _tool_ok_seen_by_trace.get(trace_id)
            if ts is None:
                return False
            if ts < (now - _TOOL_OK_TRACE_TTL_SEC):
                _tool_ok_seen_by_trace.pop(trace_id, None)
                return False
            return True
    except Exception:
        return False
