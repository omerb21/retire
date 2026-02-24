from __future__ import annotations

from app.services.llm_chat.capability_router.runtime_context import \
    RouterDecision
from app.services.llm_chat.orchestration_core.core_types import TraceEventSpec


def build_router_selected_trace_spec(
    *, trace_id: str | None, decision: RouterDecision
) -> TraceEventSpec:
    return TraceEventSpec(
        event_type="router_selected",
        trace_id=trace_id,
        payload={
            "capability_id": decision.capability_id,
            "output_schema_id": decision.output_schema_id,
            "tool_chain": list(decision.tool_chain),
            "capability_map_version": decision.capability_map_version,
            "router_normalization_version": decision.router_normalization_version,
            "normalized_text_hash": decision.normalized_text_hash,
        },
    )


def build_predicate_eval_trace_spec(
    *,
    trace_id: str | None,
    rule_id: str,
    outcome: bool,
    params_hash: str,
) -> TraceEventSpec:
    return TraceEventSpec(
        event_type="predicate_eval",
        trace_id=trace_id,
        payload={
            "rule_id": str(rule_id or ""),
            "outcome": bool(outcome),
            "params_hash": str(params_hash or ""),
        },
    )


def build_tool_started_trace_spec(
    *,
    trace_id: str | None,
    tool_id: str,
    args_hash: str,
) -> TraceEventSpec:
    return TraceEventSpec(
        event_type="tool_started",
        trace_id=trace_id,
        payload={
            "tool_id": str(tool_id or ""),
            "args_hash": str(args_hash or ""),
        },
    )


def build_tool_finished_trace_spec(
    *,
    trace_id: str | None,
    tool_id: str,
    success: bool,
    duration_ms: int,
    error_type: str | None = None,
) -> TraceEventSpec:
    payload: dict[str, object] = {
        "tool_id": str(tool_id or ""),
        "success": bool(success),
        "duration_ms": int(duration_ms),
    }
    if error_type:
        payload["error_type"] = str(error_type)
    return TraceEventSpec(
        event_type="tool_finished",
        trace_id=trace_id,
        payload=payload,
    )


def build_schema_rendered_trace_spec(
    *,
    trace_id: str | None,
    output_schema_id: str,
    result_keys: list[str],
) -> TraceEventSpec:
    return TraceEventSpec(
        event_type="schema_rendered",
        trace_id=trace_id,
        payload={
            "output_schema_id": str(output_schema_id or ""),
            "result_keys": [str(k) for k in (result_keys or [])],
        },
    )


def build_budget_guard_unenforceable_trace_spec(
    *,
    trace_id: str | None,
    guard: str,
    mode: str | None = None,
    reason: str | None = None,
) -> TraceEventSpec:
    payload: dict[str, object] = {"guard": str(guard or "")}
    if mode:
        payload["mode"] = str(mode)
    if reason:
        payload["reason"] = str(reason)
    return TraceEventSpec(
        event_type="budget_guard_unenforceable",
        trace_id=trace_id,
        payload=payload,
    )


def build_partial_returned_trace_spec(
    *,
    trace_id: str | None,
    status: str,
    detected_capability_id: str | None = None,
) -> TraceEventSpec:
    payload: dict[str, object] = {"status": str(status or "")}
    if detected_capability_id:
        payload["detected_capability_id"] = str(detected_capability_id)
    return TraceEventSpec(
        event_type="partial_returned",
        trace_id=trace_id,
        payload=payload,
    )
