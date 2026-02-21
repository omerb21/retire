from app.services.llm_chat.orchestration_core.constants import MAX_ITERATIONS_USER_MESSAGE_HE
from app.services.llm_chat.orchestration_core.core_types import (
    DecisionCode,
    OrchestrationDecision,
    PlanKind,
    TraceEventSpec,
)
from app.services.llm_chat.orchestration_core.max_iterations_guard import (
    maybe_apply_max_iterations_guard,
)


def _tool_call_decision() -> OrchestrationDecision:
    return OrchestrationDecision(
        decision_code=DecisionCode.TOOL_CALL,
        plan_kind=PlanKind.UNKNOWN,
        tool_name="SOME_TOOL",
        tool_args={},
        final_text=None,
        requires_user_approval=False,
        debug_meta=None,
    )


def test_max_iterations_guard_triggers_on_last_iteration():
    max_iterations = 4

    for iter_idx in range(max_iterations):
        decision, traces, triggered = maybe_apply_max_iterations_guard(
            iter_idx=iter_idx,
            max_iterations=max_iterations,
            trace_id="test-trace-id",
            final_text=MAX_ITERATIONS_USER_MESSAGE_HE,
            decision=OrchestrationDecision(
                decision_code=DecisionCode.TOOL_CALL,
                plan_kind=PlanKind.QA_ONLY,
                tool_name="GET_CLIENT_SNAPSHOT",
                tool_args={},
                final_text=None,
                requires_user_approval=False,
                debug_meta=None,
            ),
            trace_specs=[],
        )

        if iter_idx < max_iterations - 1:
            assert triggered is False
            assert decision.decision_code == DecisionCode.TOOL_CALL
            assert traces == []
        else:
            assert triggered is True
            assert decision.decision_code == DecisionCode.RESPOND_ONLY
            assert decision.final_text == MAX_ITERATIONS_USER_MESSAGE_HE
            assert any(
                isinstance(t, TraceEventSpec) and t.event_type == "core_final_response" for t in traces
            )
