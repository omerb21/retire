from __future__ import annotations

import threading
import time
from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(frozen=True)
class RouterDecision:
    capability_id: str
    mode: str  # "QA" | "ACTION"
    tool_chain: list[str]
    output_schema_id: str
    capability_map_version: str
    router_normalization_version: str
    normalized_text_hash: str


_current_router_decision: ContextVar[tuple[str | None, RouterDecision] | None] = (
    ContextVar("cap_router_decision", default=None)
)

_ROUTER_DECISION_TTL_SEC = 3600.0
_router_decision_by_trace: dict[str, tuple[float, RouterDecision]] = {}
_router_lock = threading.Lock()


def _prune(now: float) -> None:
    if not _router_decision_by_trace:
        return
    cutoff = now - _ROUTER_DECISION_TTL_SEC
    stale: list[str] = []
    for tid, (ts, _d) in _router_decision_by_trace.items():
        if ts < cutoff:
            stale.append(tid)
    for tid in stale:
        _router_decision_by_trace.pop(tid, None)


def set_router_decision(*, trace_id: str | None, decision: RouterDecision) -> None:
    tid = trace_id.strip() if isinstance(trace_id, str) and trace_id.strip() else None
    _current_router_decision.set((tid, decision))
    if tid is None:
        return
    try:
        now = time.monotonic()
        with _router_lock:
            _router_decision_by_trace[tid] = (now, decision)
            if len(_router_decision_by_trace) > 1000:
                _prune(now)
    except Exception:
        pass


def get_router_decision(*, trace_id: str | None) -> RouterDecision | None:
    tid = trace_id.strip() if isinstance(trace_id, str) and trace_id.strip() else None

    current = _current_router_decision.get()
    if current is not None:
        current_tid, current_decision = current
        if current_tid == tid:
            return current_decision

    if tid is None:
        return None

    try:
        now = time.monotonic()
        with _router_lock:
            item = _router_decision_by_trace.get(tid)
            if item is None:
                return None
            ts, decision = item
            if ts < (now - _ROUTER_DECISION_TTL_SEC):
                _router_decision_by_trace.pop(tid, None)
                return None
            return decision
    except Exception:
        return None


_current_router_selected_emitted: ContextVar[str | None] = ContextVar(
    "cap_router_selected_emitted", default=None
)
_router_selected_emitted_by_trace: dict[str, float] = {}
_router_selected_lock = threading.Lock()


def mark_router_selected_emitted(*, trace_id: str | None) -> None:
    tid = trace_id.strip() if isinstance(trace_id, str) and trace_id.strip() else None
    _current_router_selected_emitted.set(tid)
    if tid is None:
        return

    try:
        now = time.monotonic()
        with _router_selected_lock:
            _router_selected_emitted_by_trace[tid] = now
            if len(_router_selected_emitted_by_trace) > 1000:
                cutoff = now - _ROUTER_DECISION_TTL_SEC
                stale = [
                    k
                    for k, ts in _router_selected_emitted_by_trace.items()
                    if ts < cutoff
                ]
                for k in stale:
                    _router_selected_emitted_by_trace.pop(k, None)
    except Exception:
        pass


def was_router_selected_emitted(*, trace_id: str | None) -> bool:
    tid = trace_id.strip() if isinstance(trace_id, str) and trace_id.strip() else None
    if _current_router_selected_emitted.get() == tid and tid is not None:
        return True

    if tid is None:
        return False

    try:
        now = time.monotonic()
        with _router_selected_lock:
            ts = _router_selected_emitted_by_trace.get(tid)
            if ts is None:
                return False
            if ts < (now - _ROUTER_DECISION_TTL_SEC):
                _router_selected_emitted_by_trace.pop(tid, None)
                return False
            return True
    except Exception:
        return False
