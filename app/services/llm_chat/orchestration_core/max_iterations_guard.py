from __future__ import annotations

from .constants import MAX_ITERATIONS_USER_MESSAGE_HE
from .core_types import DecisionCode, OrchestrationDecision, PlanKind, TraceEventSpec


def should_trigger_max_iterations_guard(*, iter_idx: int, max_iterations: int) -> bool:
    try:
        return int(iter_idx) >= int(max_iterations) - 1
    except Exception:
        return False


def build_max_iterations_guard_decision_and_traces(
    *,
    final_text: str = MAX_ITERATIONS_USER_MESSAGE_HE,
) -> tuple[OrchestrationDecision, list[TraceEventSpec]]:
    decision = OrchestrationDecision(
        decision_code=DecisionCode.RESPOND_ONLY,
        plan_kind=PlanKind.UNKNOWN,
        tool_name=None,
        tool_args=None,
        final_text=final_text,
        requires_user_approval=False,
        debug_meta=None,
    )
    trace_specs = [
        TraceEventSpec(
            event_type="core_final_response",
            payload={"reply_preview": str(final_text)[:500]},
        )
    ]
    return decision, trace_specs


def maybe_apply_max_iterations_guard(
    *,
    iter_idx: int,
    max_iterations: int,
    final_text: str = MAX_ITERATIONS_USER_MESSAGE_HE,
    decision: OrchestrationDecision,
    trace_specs: list[TraceEventSpec],
) -> tuple[OrchestrationDecision, list[TraceEventSpec], bool]:
    if getattr(decision, "decision_code", None) != DecisionCode.TOOL_CALL:
        return decision, trace_specs, False

    if not should_trigger_max_iterations_guard(iter_idx=iter_idx, max_iterations=max_iterations):
        return decision, trace_specs, False

    guard_decision, guard_traces = build_max_iterations_guard_decision_and_traces(final_text=final_text)
    merged_traces = list(trace_specs or []) + list(guard_traces or [])
    return guard_decision, merged_traces, True
