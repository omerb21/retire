from __future__ import annotations

import json
from datetime import date, datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

import app.services.llm_chat.chat_orchestration_parts.orchestrator_impl_parts.steps_parts.runner_step_handlers as runner_step_handlers
import app.services.llm_chat.chat_stream_orchestration as stream_orch
import app.services.llm_chat.chat_stream_orchestration_parts.stream_system_prompt_generators as stream_prompt_mod
from app.main import app
from app.models import Scenario
from app.models.pension_fund import PensionFund
from app.schemas.llm_chat import ChatMessage, ChatRequest
from app.services.llm_chat.chat_orchestration_helpers_parts.scenario_storage import (
    clear_execution_veto,
    load_execution_veto,
    load_normalized_target_plan_context,
    store_execution_veto,
    store_latest_target_pension_plan_data,
    store_normalized_target_plan_context,
    store_pending_approval_request,
)
from app.services.llm_chat.chat_stream_orchestration_parts.stream_approval_generators import (
    generate_forced_approval,
)
from app.services.llm_chat.chat_stream_orchestration_parts.stream_system_prompt_generators import (
    generate_cashflow,
    generate_target_plan,
)
from app.services.llm_chat.orchestration_core.canonical_action_selector import (
    ACTION_ANSWER_GENERAL_QUESTION,
    ACTION_COMPARE_EXISTING_PLANS,
    ACTION_GREETING_AND_MENU,
    ACTION_PLAN_RETIREMENT,
)
from app.services.llm_chat.orchestration_core.core_types import (
    FeatureFlagKey,
    OrchestrationDeps,
    OrchestrationInput,
)


class _TraceCapture:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def fake_log_trace_event(
        self, *, trace_id=None, event_type: str, payload=None, **kwargs
    ) -> None:
        _ = kwargs
        self.events.append(
            {"trace_id": trace_id, "event_type": event_type, "payload": payload}
        )

    def find_first_payload(
        self, event_type: str, trace_id: str | None = None
    ) -> dict[str, Any]:
        for event in self.events:
            if event.get("event_type") != event_type:
                continue
            if trace_id is not None and event.get("trace_id") != trace_id:
                continue
            payload = event.get("payload")
            if isinstance(payload, dict):
                return payload
        trace_label = trace_id if trace_id is not None else "<any trace>"
        raise AssertionError(f"Missing trace event `{event_type}` for {trace_label}.")

    def find_last_payload(
        self, event_type: str, trace_id: str | None = None
    ) -> dict[str, Any]:
        matches: list[dict[str, Any]] = []
        for event in self.events:
            if event.get("event_type") != event_type:
                continue
            if trace_id is not None and event.get("trace_id") != trace_id:
                continue
            payload = event.get("payload")
            if isinstance(payload, dict):
                matches.append(payload)
        if matches:
            return matches[-1]
        trace_label = trace_id if trace_id is not None else "<any trace>"
        raise AssertionError(f"Missing trace event `{event_type}` for {trace_label}.")


def _install_trace_capture(monkeypatch) -> _TraceCapture:
    import app.services.agent_execution.execute_agent_request as entry_mod
    import app.services.agent_execution.tool_executor as tool_exec_mod
    import app.services.agent_trace_logger as trace_logger_mod
    import app.services.llm_chat.capability_router.router_facade as router_facade_mod
    import app.services.llm_chat.tool_execution as tool_execution_mod

    capture = _TraceCapture()
    monkeypatch.setattr(entry_mod, "log_trace_event", capture.fake_log_trace_event)
    monkeypatch.setattr(tool_exec_mod, "log_trace_event", capture.fake_log_trace_event)
    monkeypatch.setattr(
        trace_logger_mod, "log_trace_event", capture.fake_log_trace_event
    )
    monkeypatch.setattr(
        router_facade_mod, "log_trace_event", capture.fake_log_trace_event
    )
    monkeypatch.setattr(
        tool_execution_mod, "_log_agent_trace", capture.fake_log_trace_event
    )
    return capture


def _build_deps() -> OrchestrationDeps:
    return OrchestrationDeps(
        llm_generate=lambda _messages, _client_id=None: "",
        tool_defaults=lambda _tool_name: {},
    )


def _find_trace_spec_payload(trace_specs, event_type: str) -> dict[str, Any]:
    for spec in trace_specs:
        if getattr(spec, "event_type", None) != event_type:
            continue
        payload = getattr(spec, "payload", None)
        if isinstance(payload, dict):
            return payload
    raise AssertionError(f"Missing trace spec `{event_type}`.")


def _find_capability_resolved_with_canonical_action(
    capture: _TraceCapture, trace_id: str
) -> dict[str, Any]:
    for event in capture.events:
        if event.get("event_type") != "capability_resolved":
            continue
        if event.get("trace_id") != trace_id:
            continue
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        if str(payload.get("canonical_action") or "").strip():
            return payload
    raise AssertionError(
        "Missing router-backed `capability_resolved` event with canonical_action "
        f"for {trace_id}."
    )


def _assert_required_keys(
    payload: dict[str, Any], required_keys: tuple[str, ...], context: str
) -> None:
    missing = [key for key in required_keys if key not in payload]
    assert not missing, f"{context} is missing required keys: {missing}."


@pytest.mark.parametrize(
    ("scenario_name", "user_text", "feature_flags", "expected_action"),
    [
        (
            "greeting path",
            "שלום",
            {FeatureFlagKey.GREETING_SHORTCUT: True},
            ACTION_GREETING_AND_MENU,
        ),
        ("planning path", "ניתוח ותיזמון פרישה", {}, ACTION_PLAN_RETIREMENT),
        (
            "compare path",
            "השווה בין שתי תכניות",
            {},
            ACTION_COMPARE_EXISTING_PLANS,
        ),
    ],
)
def test_core_trace_contracts_for_primary_paths(
    scenario_name: str,
    user_text: str,
    feature_flags: dict[FeatureFlagKey, bool],
    expected_action: str,
) -> None:
    import app.services.llm_chat.orchestration_core.orchestrate as orch_mod

    decision, trace_specs = orch_mod.orchestrate(
        OrchestrationInput(
            user_text=user_text,
            client_id=1,
            session_id=None,
            conversation_id=None,
            trace_id=f"trace_{scenario_name.replace(' ', '_')}",
            feature_flags=feature_flags,
            request_meta=None,
            state_snapshot={},
            last_tool_result=None,
        ),
        _build_deps(),
    )

    _ = decision
    canonical_payload = _find_trace_spec_payload(
        trace_specs, "core_canonical_action_selected"
    )
    _assert_required_keys(
        canonical_payload,
        ("action", "reason_code", "source_signals"),
        f"core_canonical_action_selected in {scenario_name}",
    )
    assert canonical_payload["action"] == expected_action, (
        f"Unexpected canonical action in {scenario_name}: "
        f"expected `{expected_action}`, got `{canonical_payload['action']}`."
    )
    assert str(
        canonical_payload["reason_code"]
    ).strip(), (
        f"core_canonical_action_selected.reason_code is empty in {scenario_name}."
    )
    assert isinstance(
        canonical_payload["source_signals"], list
    ), f"core_canonical_action_selected.source_signals must be a list in {scenario_name}."

    next_action_payload = _find_trace_spec_payload(
        trace_specs, "core_next_action_decided"
    )
    _assert_required_keys(
        next_action_payload,
        ("decision_code", "plan_kind"),
        f"core_next_action_decided in {scenario_name}",
    )
    assert str(
        next_action_payload["decision_code"]
    ).strip(), f"core_next_action_decided.decision_code is empty in {scenario_name}."
    assert str(
        next_action_payload["plan_kind"]
    ).strip(), f"core_next_action_decided.plan_kind is empty in {scenario_name}."


def test_monthly_pension_trace_continuity_contract(
    db_session, client, monkeypatch
) -> None:
    from app.services.agent_execution.execute_agent_request import execute_agent_request
    from app.services.llm_chat.capability_router.ssot_loader import load_capability_map
    from app.utils.trace_context import set_current_trace_id

    db_session.query(PensionFund).filter(PensionFund.client_id == client.id).delete(
        synchronize_session=False
    )
    db_session.commit()
    db_session.add(
        PensionFund(
            client_id=client.id,
            fund_name="MP-TRACE-1",
            fund_type="monthly_pension",
            input_mode="manual",
            pension_amount=1000.0,
            pension_start_date=date(2020, 1, 1),
            indexation_method="none",
            tax_treatment="taxable",
        )
    )
    db_session.commit()

    monkeypatch.setenv(
        "CAPABILITY_MAP_PATH", "tests/fixtures/stage16/capability_map_stage16.yaml"
    )
    load_capability_map.cache_clear()
    capture = _install_trace_capture(monkeypatch)

    trace_id = "trace_monthly_pension_trace_continuity"
    set_current_trace_id(trace_id)
    try:
        db_session.info["trace_id"] = trace_id
    except Exception:
        pass

    res = execute_agent_request(
        ChatRequest(
            messages=[ChatMessage(role="user", content="קצבה חודשית")],
            client_id=int(client.id),
            pension_portfolio=None,
        ),
        db_session,
    )

    canonical_payload = capture.find_first_payload(
        "core_canonical_action_selected", trace_id
    )
    capability_payload = _find_capability_resolved_with_canonical_action(
        capture, trace_id
    )
    router_payload = capture.find_first_payload("router_selected", trace_id)

    _assert_required_keys(
        canonical_payload,
        ("action", "reason_code", "source_signals"),
        "core_canonical_action_selected in monthly pension path",
    )
    _assert_required_keys(
        capability_payload,
        ("capability_id", "decision_source", "canonical_action"),
        "capability_resolved in monthly pension path",
    )
    _assert_required_keys(
        router_payload,
        ("capability_id", "output_schema_id", "tool_chain"),
        "router_selected in monthly pension path",
    )

    assert (
        canonical_payload["action"] == ACTION_ANSWER_GENERAL_QUESTION
    ), "Monthly pension path lost the expected canonical action marker."
    assert (
        capability_payload["capability_id"] == "monthly_pension_summary_action_v1"
    ), "Monthly pension path lost the dedicated capability_resolved capability_id."
    assert (
        capability_payload["decision_source"] == "ssot_runtime_router"
    ), "Monthly pension path lost the expected capability_resolved decision_source."
    assert capability_payload["canonical_action"] == canonical_payload["action"], (
        "Monthly pension path lost canonical-action continuity between "
        "core_canonical_action_selected and capability_resolved."
    )
    assert router_payload["capability_id"] == capability_payload["capability_id"], (
        "Monthly pension path lost capability continuity between capability_resolved "
        "and router_selected."
    )
    assert str(
        router_payload["output_schema_id"]
    ).strip(), "Monthly pension path emitted router_selected without output_schema_id."
    assert router_payload["tool_chain"] == [
        "MONTHLY_PENSION_SUMMARY"
    ], "Monthly pension path emitted an unexpected router_selected.tool_chain."
    computed_data = getattr(res, "computed_data", None)
    assert isinstance(
        computed_data, dict
    ), "Monthly pension path stopped returning computed_data for diagnostics coverage."


def test_system_only_stream_router_selected_trace_contract(monkeypatch) -> None:
    capture = _install_trace_capture(monkeypatch)

    def fake_chat_stream(messages, client_id=None):
        _ = (messages, client_id)
        raise AssertionError("LLM should not be called for system-only stream path")

    tool_calls: list[str] = []

    def fake_execute_tool_call(
        *,
        tool_name: str,
        args: dict,
        client_id: int,
        db,
        pension_portfolio=None,
        force_max_exemption: bool = False,
    ) -> str:
        _ = (args, client_id, db, pension_portfolio, force_max_exemption)
        tool_calls.append(tool_name)
        return '{"products": [{"category": "pension", "fund_name": "פנסיה א", "balance": 1000}]}'

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )
    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)
    monkeypatch.setattr(
        stream_orch,
        "load_latest_pension_portfolio_snapshot_models",
        lambda db, client_id: None,
    )

    response = TestClient(app).post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [{"role": "user", "content": 'מה גובה סה"כ הקצבה כעת?'}],
        },
    )

    assert response.status_code == 200
    assert tool_calls == ["GET_PENSION_PRODUCTS"]
    router_payload = capture.find_last_payload("router_selected")
    _assert_required_keys(
        router_payload,
        ("capability_id", "output_schema_id", "tool_chain"),
        "router_selected in system-only stream path",
    )
    assert str(
        router_payload["output_schema_id"]
    ).strip(), (
        "System-only stream path emitted router_selected without output_schema_id."
    )
    assert isinstance(
        router_payload["tool_chain"], list
    ), "System-only stream path emitted router_selected.tool_chain in a non-list shape."


def test_legacy_fallback_trace_contract_is_diagnostic(monkeypatch, db_session) -> None:
    import app.services.llm_chat.chat_orchestration as chat_orch
    from app.services.agent_execution import execute_agent_request as exec_mod
    from app.services.llm_chat.orchestration_core.core_types import (
        DecisionCode,
        OrchestrationDecision,
        PlanKind,
    )

    capture = _install_trace_capture(monkeypatch)

    monkeypatch.setattr(
        exec_mod,
        "ensure_router_decision",
        lambda **kwargs: type("_D", (), {"capability_id": "default_qa_v1"})(),
    )

    def fake_orchestrate(_inp, _deps):
        return (
            OrchestrationDecision(
                decision_code=DecisionCode.RESPOND_ONLY,
                plan_kind=PlanKind.UNKNOWN,
                tool_name=None,
                tool_args=None,
                final_text="",
                requires_user_approval=False,
                debug_meta={"legacy_fallback": True},
            ),
            [],
        )

    def passthrough_max_iter_guard(
        *, iter_idx, max_iterations, trace_id, final_text, decision, trace_specs
    ):
        _ = (iter_idx, max_iterations, trace_id, final_text)
        return decision, trace_specs, False

    monkeypatch.setattr(exec_mod, "orchestrate", fake_orchestrate)
    monkeypatch.setattr(
        exec_mod, "maybe_apply_max_iterations_guard", passthrough_max_iter_guard
    )
    monkeypatch.setattr(
        chat_orch,
        "run_pension_chat",
        lambda *args, **kwargs: exec_mod.ChatResponse(
            reply="legacy", computed_data=None
        ),
    )

    res = exec_mod.execute_agent_request(
        ChatRequest(messages=[ChatMessage(role="user", content="hi")], client_id=1),
        db_session,
    )

    assert getattr(res, "reply", None) == "legacy"
    legacy_payload = capture.find_first_payload("legacy_fallback_entered")
    _assert_required_keys(
        legacy_payload,
        ("execution_path", "reason", "legacy_reason_code"),
        "legacy_fallback_entered",
    )
    assert (
        legacy_payload["execution_path"] == "legacy_fallback"
    ), "legacy_fallback_entered.execution_path lost the legacy_fallback marker."
    assert str(
        legacy_payload["reason"]
    ).strip(), "legacy_fallback_entered.reason is empty."
    assert (
        legacy_payload["reason"] != "fallback"
    ), "legacy_fallback_entered.reason became too generic to diagnose failures."
    assert str(legacy_payload["reason"]).startswith(
        "core_decision_code:"
    ), "legacy_fallback_entered.reason no longer explains which core decision triggered fallback."
    assert str(
        legacy_payload["legacy_reason_code"]
    ).strip(), "legacy_fallback_entered.legacy_reason_code is empty."


@pytest.mark.parametrize(
    (
        "trace_id",
        "user_text",
        "expected_event_type",
        "expected_requested_execution",
        "expected_mapping_is_unambiguous",
    ),
    [
        (
            "trace_termination_parser_planning_contract",
            "אני רוצה להבין אפשרויות של עזיבת עבודה",
            "termination_parser_planning_blocked",
            False,
            True,
        ),
        (
            "trace_termination_parser_missing_requested_execution_contract",
            "termination",
            "termination_parser_missing_requested_execution_blocked",
            False,
            True,
        ),
        (
            "trace_termination_parser_ambiguous_mapping_contract",
            "הכל למשיכה ללא פטור",
            "termination_parser_ambiguous_mapping_blocked",
            True,
            False,
        ),
    ],
)
def test_termination_parser_trace_contracts(
    db_session,
    client,
    monkeypatch,
    trace_id: str,
    user_text: str,
    expected_event_type: str,
    expected_requested_execution: bool,
    expected_mapping_is_unambiguous: bool,
) -> None:
    capture = _install_trace_capture(monkeypatch)

    db_session.query(Scenario).filter(Scenario.client_id == client.id).filter(
        Scenario.scenario_name == "pending_approval"
    ).delete(synchronize_session=False)
    db_session.commit()

    _ = "".join(
        generate_forced_approval(
            computed_data=None,
            explicit_termination=True,
            termination_already_executed=False,
            request=ChatRequest(
                client_id=int(client.id),
                messages=[ChatMessage(role="user", content=user_text)],
                pension_portfolio=[],
            ),
            db=db_session,
            effective_portfolio=[],
            force_max_exemption=False,
            stream_request_id=trace_id,
            wants_execute_target_plan=False,
            wants_fixation_execute=False,
        )
    )

    payload = capture.find_first_payload(expected_event_type, trace_id)
    _assert_required_keys(
        payload,
        (
            "planning_only",
            "explicit_execution_intent",
            "explicit_execution_veto",
            "reason_code",
            "requested_execution",
            "mapping_is_unambiguous",
            "tool_name",
            "has_exempt_choice",
            "has_taxable_choice",
        ),
        expected_event_type,
    )
    assert payload["tool_name"] == "PROCESS_TERMINATION"
    assert payload["requested_execution"] is expected_requested_execution
    assert payload["mapping_is_unambiguous"] is expected_mapping_is_unambiguous


def _clear_compare_target_plan_trace(db_session, *, client_id: int) -> None:
    db_session.query(Scenario).filter(Scenario.client_id == client_id).filter(
        Scenario.scenario_name.in_(("target_pension_plan", "target_pension_plan_data"))
    ).delete(synchronize_session=False)
    db_session.commit()


def _seed_compare_target_plan_trace(
    db_session, *, client_id: int, retirement_age: int
) -> None:
    payload = {
        "tool_name": "BUILD_TARGET_PENSION_PLAN",
        "args": {
            "target_monthly_pension": 30000,
            "target_is_net": True,
            "retirement_age": retirement_age,
        },
        "result": {
            "target_monthly_pension": 30000,
            "target_is_net": True,
            "retirement_age": retirement_age,
            "estimated_monthly_net": 29000,
            "estimated_monthly_tax": 1000,
            "remaining_capital": 100000,
            "execution_plan": {"expected_total_gross": 30000},
        },
        "_meta": {"stored_at_utc": datetime.now(timezone.utc).isoformat()},
    }
    for scenario_name in ("target_pension_plan", "target_pension_plan_data"):
        db_session.add(
            Scenario(
                client_id=client_id,
                scenario_name=scenario_name,
                apply_tax_planning=False,
                apply_capitalization=False,
                apply_exemption_shield=False,
                parameters=json.dumps(payload, ensure_ascii=False),
                created_at=datetime.now(timezone.utc),
            )
        )
    db_session.commit()


def test_compare_trace_contract_ambiguous_without_session_anchor(
    db_session, client, monkeypatch
) -> None:
    from app.utils.trace_context import set_current_trace_id

    capture = _install_trace_capture(monkeypatch)
    monkeypatch.setattr(
        stream_orch.pension_llm_service,
        "chat_stream",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("LLM must not run")
        ),
    )
    _clear_compare_target_plan_trace(db_session, client_id=int(client.id))
    trace_id = "trace_compare_contract_ambiguous"
    set_current_trace_id(trace_id)
    try:
        db_session.info["trace_id"] = trace_id
    except Exception:
        pass

    response = TestClient(app).post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": int(client.id),
            "messages": [
                {
                    "role": "user",
                    "content": "מה ההבדל בין התכנית של גיל 72 לתכנית של גיל 76",
                }
            ],
        },
    )

    assert response.status_code == 200
    assert "כדי לבנות תכנית פרישה אני צריך יעד חודשי נטו" not in response.text
    assert capture.find_first_payload("retirement_compare_detected") == {
        "detected": True
    }
    assert capture.find_first_payload("retirement_compare_blocked_target_prompt") == {
        "blocked_branch": "target_prompt"
    }
    ambiguous_payload = capture.find_first_payload("retirement_compare_ambiguous")
    _assert_required_keys(
        ambiguous_payload,
        ("ambiguity_reason",),
        "retirement_compare_ambiguous",
    )


def test_compare_trace_contract_needs_reference_and_ready(
    db_session, client, monkeypatch
) -> None:
    from app.utils.trace_context import set_current_trace_id

    monkeypatch.setattr(
        stream_orch.pension_llm_service,
        "chat_stream",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("LLM must not run")
        ),
    )

    _clear_compare_target_plan_trace(db_session, client_id=int(client.id))
    _seed_compare_target_plan_trace(
        db_session, client_id=int(client.id), retirement_age=72
    )
    capture_one = _install_trace_capture(monkeypatch)
    trace_id_one = "trace_compare_contract_needs_reference"
    set_current_trace_id(trace_id_one)
    try:
        db_session.info["trace_id"] = trace_id_one
    except Exception:
        pass
    response_one = TestClient(app).post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": int(client.id),
            "messages": [{"role": "user", "content": "תעשה השוואה בין שתי התכניות"}],
        },
    )
    assert response_one.status_code == 200
    needs_payload = capture_one.find_first_payload("retirement_compare_needs_reference")
    _assert_required_keys(
        needs_payload,
        ("reference_count",),
        "retirement_compare_needs_reference",
    )
    assert needs_payload["reference_count"] == 1

    _seed_compare_target_plan_trace(
        db_session, client_id=int(client.id), retirement_age=76
    )
    capture_two = _install_trace_capture(monkeypatch)
    trace_id_two = "trace_compare_contract_ready"
    set_current_trace_id(trace_id_two)
    try:
        db_session.info["trace_id"] = trace_id_two
    except Exception:
        pass
    response_two = TestClient(app).post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": int(client.id),
            "messages": [{"role": "user", "content": "תעשה השוואה בין שתי התכניות"}],
        },
    )
    assert response_two.status_code == 200
    ready_payload = capture_two.find_first_payload("retirement_compare_ready")
    _assert_required_keys(
        ready_payload,
        ("reference_count",),
        "retirement_compare_ready",
    )
    assert ready_payload["reference_count"] == 2


def _count_trace_events(capture: _TraceCapture, event_type: str, trace_id: str) -> int:
    return sum(
        1
        for event in capture.events
        if event.get("event_type") == event_type and event.get("trace_id") == trace_id
    )


def test_advisory_trace_contract_general(db_session, client, monkeypatch) -> None:
    capture = _install_trace_capture(monkeypatch)
    db_session.query(Scenario).filter(Scenario.client_id == int(client.id)).filter(
        Scenario.scenario_name.in_(
            ("normalized_target_plan_context", "pending_approval")
        )
    ).delete(synchronize_session=False)
    db_session.commit()

    trace_id = "trace_stage_f_advisory_contract_general"
    db_session.info["trace_id"] = trace_id
    request = SimpleNamespace(
        client_id=int(client.id),
        trace_id=trace_id,
        messages=[SimpleNamespace(role="user", content="מה אתה יכול להמליץ לי?")],
    )
    reply = runner_step_handlers._build_local_no_tool_reply(
        request=request,
        db=db_session,
        request_id=trace_id,
        original_user_msg="מה אתה יכול להמליץ לי?",
        is_comparison_request=False,
        has_tool_results=False,
        raw_reply="fallback",
    )
    assert isinstance(reply, str) and reply.strip()
    assert capture.find_first_payload("advisory_mode_detected", trace_id) == {
        "advisory_intent": True
    }
    assert capture.find_first_payload("advisory_mode_general", trace_id) == {
        "has_target_context": False,
        "has_pending_state": False,
    }
    built_payload = capture.find_first_payload("advisory_mode_response_built", trace_id)
    assert built_payload.get("mode") == "ADVISORY_GENERAL"
    assert int(built_payload.get("option_count") or 0) in (2, 3, 4)

    assert _count_trace_events(capture, "advisory_mode_general", trace_id) == 1
    assert (
        _count_trace_events(capture, "advisory_mode_contextual_target", trace_id) == 0
    )
    assert (
        _count_trace_events(capture, "advisory_mode_contextual_pending_state", trace_id)
        == 0
    )


def test_advisory_trace_contract_contextual_target(
    db_session, client, monkeypatch
) -> None:
    capture = _install_trace_capture(monkeypatch)

    db_session.query(Scenario).filter(Scenario.client_id == int(client.id)).filter(
        Scenario.scenario_name.in_(
            ("normalized_target_plan_context", "pending_approval")
        )
    ).delete(synchronize_session=False)
    db_session.commit()
    assert (
        store_normalized_target_plan_context(
            db=db_session,
            client_id=int(client.id),
            requested_target=30000,
            target_mode="net",
            offset_used=0,
            effective_target=30000,
            retirement_age=76,
            trace_id="trace_stage_f_seed_target_ctx",
        )
        is True
    )

    trace_id = "trace_stage_f_advisory_contract_contextual_target"
    db_session.info["trace_id"] = trace_id
    request = SimpleNamespace(
        client_id=int(client.id),
        trace_id=trace_id,
        messages=[SimpleNamespace(role="user", content="מה תמליץ לי?")],
    )
    reply = runner_step_handlers._build_local_no_tool_reply(
        request=request,
        db=db_session,
        request_id=trace_id,
        original_user_msg="מה תמליץ לי?",
        is_comparison_request=False,
        has_tool_results=False,
        raw_reply="fallback",
    )
    assert isinstance(reply, str) and reply.strip()
    assert capture.find_first_payload("advisory_mode_contextual_target", trace_id) == {
        "has_target_context": True,
        "has_pending_state": False,
    }
    built_payload = capture.find_first_payload("advisory_mode_response_built", trace_id)
    assert built_payload.get("mode") == "ADVISORY_CONTEXTUAL_TARGET"
    assert int(built_payload.get("option_count") or 0) in (2, 3, 4)
    assert (
        _count_trace_events(capture, "advisory_mode_contextual_target", trace_id) == 1
    )


def test_advisory_trace_contract_contextual_pending_state(
    db_session, client, monkeypatch
) -> None:
    capture = _install_trace_capture(monkeypatch)

    db_session.query(Scenario).filter(Scenario.client_id == int(client.id)).filter(
        Scenario.scenario_name.in_(
            ("normalized_target_plan_context", "pending_approval")
        )
    ).delete(synchronize_session=False)
    db_session.commit()
    assert (
        store_pending_approval_request(
            db=db_session,
            client_id=int(client.id),
            tool_name="TRANSFORM_FUNDS_TO_ASSETS",
            tool_args={
                "approval_id": "trace_stage_f_pending",
                "approval_type": "execution",
            },
        )
        is True
    )

    trace_id = "trace_stage_f_advisory_contract_contextual_pending"
    db_session.info["trace_id"] = trace_id
    request = SimpleNamespace(
        client_id=int(client.id),
        trace_id=trace_id,
        messages=[SimpleNamespace(role="user", content="מה כדאי לעשות?")],
    )
    reply = runner_step_handlers._build_local_no_tool_reply(
        request=request,
        db=db_session,
        request_id=trace_id,
        original_user_msg="מה כדאי לעשות?",
        is_comparison_request=False,
        has_tool_results=False,
        raw_reply="fallback",
    )
    assert isinstance(reply, str) and reply.strip()
    assert capture.find_first_payload(
        "advisory_mode_contextual_pending_state", trace_id
    ) == {
        "has_target_context": False,
        "has_pending_state": True,
    }
    built_payload = capture.find_first_payload("advisory_mode_response_built", trace_id)
    assert built_payload.get("mode") == "ADVISORY_CONTEXTUAL_PENDING_STATE"
    assert int(built_payload.get("option_count") or 0) in (2, 3, 4)
    assert (
        _count_trace_events(capture, "advisory_mode_contextual_pending_state", trace_id)
        == 1
    )
