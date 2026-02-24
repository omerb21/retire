from __future__ import annotations

from app.services.llm_chat.capability_router.resolver import resolve
from app.services.llm_chat.capability_router.runtime_context import (
    RouterDecision, get_router_decision, mark_router_selected_emitted,
    set_router_decision, was_router_selected_emitted)
from app.services.llm_chat.capability_router.trace_specs import \
    build_router_selected_trace_spec


def ensure_router_decision(
    *, user_text: str, client_id: int | None, trace_id: str | None
) -> RouterDecision:
    existing = get_router_decision(trace_id=trace_id)
    if existing is not None:
        return existing

    decision = resolve(user_text=user_text, client_id=client_id, trace_id=trace_id)
    set_router_decision(trace_id=trace_id, decision=decision)
    return decision


def maybe_emit_router_selected_trace(*, trace_id: str | None, decision: RouterDecision):
    if was_router_selected_emitted(trace_id=trace_id):
        return None
    mark_router_selected_emitted(trace_id=trace_id)
    return build_router_selected_trace_spec(trace_id=trace_id, decision=decision)
