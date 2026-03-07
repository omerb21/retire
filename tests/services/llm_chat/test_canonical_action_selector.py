from __future__ import annotations

from app.services.llm_chat.orchestration_core.canonical_action_selector import (
    ACTION_ANSWER_GENERAL_QUESTION,
    ACTION_COMPARE_EXISTING_PLANS,
    ACTION_GREETING_AND_MENU,
    ACTION_PLAN_RETIREMENT,
    ACTION_TERMINATION_EXECUTION,
    ACTION_TERMINATION_PRECHECK,
    CanonicalActionDecision,
    is_canonical_action,
    select_canonical_action,
)
from app.services.llm_chat.orchestration_core.core_types import (
    OrchestrationDeps,
    OrchestrationInput,
)
from app.services.llm_chat.orchestration_core.orchestrate import orchestrate


def test_select_canonical_action_returns_only_allowed_actions() -> None:
    cases = [
        "שלום",
        "מה ההבדל בין פרישה בגיל 67 ל-70?",
        "בנה לי תכנית פרישה ל-30000 נטו",
        "תשווה בין פרישה עכשיו לבין עוד שנה",
        "בצע עזיבת עבודה",
        "אני מאשר process_termination",
    ]

    for user_text in cases:
        decision = select_canonical_action(user_text=user_text)
        assert is_canonical_action(decision.action)


def test_select_canonical_action_detects_greeting() -> None:
    decision = select_canonical_action(user_text="שלום")

    assert decision.action == ACTION_GREETING_AND_MENU
    assert decision.reason_code == "greeting_detected"


def test_select_canonical_action_detects_planning() -> None:
    decision = select_canonical_action(user_text="בנה לי תכנית פרישה ל-30000 נטו")

    assert decision.action == ACTION_PLAN_RETIREMENT
    assert decision.reason_code == "planning_or_simulation_request"


def test_select_canonical_action_detects_compare() -> None:
    decision = select_canonical_action(user_text="תשווה בין פרישה בגיל 67 ל-70")

    assert decision.action == ACTION_COMPARE_EXISTING_PLANS
    assert decision.reason_code == "compare_existing_plans"


def test_select_canonical_action_termination_without_approval_returns_precheck() -> (
    None
):
    decision = select_canonical_action(user_text="בצע עזיבת עבודה עכשיו")

    assert decision.action == ACTION_TERMINATION_PRECHECK
    assert decision.reason_code == "explicit_termination_execution_missing_approval"


def test_select_canonical_action_termination_with_approval_returns_execution() -> None:
    decision = select_canonical_action(
        user_text="מאשר",
        state_snapshot={
            "approval_request_already_sent": True,
            "pending_approval_tool_name": "PROCESS_TERMINATION",
        },
    )

    assert decision.action == ACTION_TERMINATION_EXECUTION
    assert decision.reason_code == "explicit_termination_execution_approved"


def test_select_canonical_action_defaults_to_general_question() -> None:
    decision = select_canonical_action(user_text="מה אפשר לעשות במקרה כזה?")

    assert decision.action == ACTION_ANSWER_GENERAL_QUESTION
    assert decision.reason_code == "general_question_default"


def test_orchestrate_calls_select_canonical_action(monkeypatch) -> None:
    import app.services.llm_chat.orchestration_core.orchestrate as orchestrate_module

    calls: list[dict] = []

    def fake_select_canonical_action(
        *, user_text: str, state_snapshot=None, last_tool_name=None
    ):
        calls.append(
            {
                "user_text": user_text,
                "state_snapshot": state_snapshot,
                "last_tool_name": last_tool_name,
            }
        )
        return CanonicalActionDecision(
            action=ACTION_GREETING_AND_MENU,
            reason_code="test_spy",
            source_signals=("test.spy",),
        )

    monkeypatch.setattr(
        orchestrate_module,
        "select_canonical_action",
        fake_select_canonical_action,
        raising=True,
    )

    deps = OrchestrationDeps(
        llm_generate=lambda _messages, _client_id=None: "",
        tool_defaults=lambda _tool_name: {},
    )
    core_input = OrchestrationInput(
        user_text="שלום",
        client_id=1,
        session_id=None,
        conversation_id=None,
        trace_id="trace_canonical_action_selector_test",
        feature_flags={},
        request_meta=None,
        state_snapshot={},
        last_tool_result=None,
    )

    decision, trace_specs = orchestrate(core_input, deps)

    assert len(calls) == 1
    assert calls[0]["user_text"] == "שלום"
    assert isinstance(decision.debug_meta, dict)
    assert decision.debug_meta.get("canonical_action") == ACTION_GREETING_AND_MENU
    canonical_events = [
        spec
        for spec in trace_specs
        if spec.event_type == "core_canonical_action_selected"
    ]
    assert len(canonical_events) == 1
    assert canonical_events[0].payload["action"] == ACTION_GREETING_AND_MENU
