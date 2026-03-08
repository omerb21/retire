import json
from datetime import date
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

import app.services.llm_chat.chat_orchestration as chat_orch
import app.services.llm_chat.chat_stream_orchestration as stream_orch
import app.services.llm_chat.chat_stream_orchestration_parts.stream_system_prompt_generators as stream_prompt_mod
from app.main import app
from app.models import Scenario
from app.models.pension_fund import PensionFund
from app.schemas.llm_chat import ChatMessage, ChatRequest
from app.services.llm_chat.chat_orchestration_helpers_parts.scenario_storage import (
    load_execution_veto,
    load_normalized_target_plan_context,
    store_execution_veto,
    store_pending_approval_request,
)
from app.services.llm_chat.chat_stream_orchestration_parts.orchestrator_impl_parts.stream_loop_approval_cancel_handling import (
    _maybe_handle_approval_or_cancel_flow,
)
from app.services.llm_chat.chat_stream_orchestration_parts.stream_approval_generators import (
    generate_forced_approval,
)
from app.services.llm_chat.chat_stream_orchestration_parts.stream_system_prompt_generators import (
    generate_target_plan,
)
from app.services.llm_chat.orchestration_core.canonical_action_selector import (
    ACTION_ANSWER_GENERAL_QUESTION,
    ACTION_COMPARE_EXISTING_PLANS,
    ACTION_GREETING_AND_MENU,
    ACTION_PLAN_RETIREMENT,
    select_canonical_action,
)
from app.services.llm_chat.orchestration_utils_parts.guards_and_validations import (
    decide_stream_planning_execution_policy,
    is_process_termination_request,
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

    def find_router_selected(self, trace_id: str) -> dict[str, Any]:
        for event in self.events:
            if event.get("trace_id") != trace_id:
                continue
            if event.get("event_type") != "router_selected":
                continue
            payload = event.get("payload")
            if isinstance(payload, dict):
                return payload
        raise AssertionError("router_selected event not found")

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
        raise AssertionError(f"Missing trace event `{event_type}`.")


def _install_trace_capture(monkeypatch) -> _TraceCapture:
    import app.services.agent_execution.execute_agent_request as entry_mod
    import app.services.agent_execution.tool_executor as tool_exec_mod
    import app.services.agent_trace_logger as trace_logger_mod
    import app.services.llm_chat.tool_execution as tool_execution_mod

    capture = _TraceCapture()
    monkeypatch.setattr(entry_mod, "log_trace_event", capture.fake_log_trace_event)
    monkeypatch.setattr(tool_exec_mod, "log_trace_event", capture.fake_log_trace_event)
    monkeypatch.setattr(
        trace_logger_mod, "log_trace_event", capture.fake_log_trace_event
    )
    monkeypatch.setattr(
        tool_execution_mod, "_log_agent_trace", capture.fake_log_trace_event
    )
    return capture


def test_non_stream_portfolio_short_summary_uses_short_summary_path_not_system_only(
    monkeypatch,
) -> None:
    def fake_chat(messages, client_id=None):
        return '###TRANSPARENCY_LOG### {"test": true}\n###RISK_REVIEW### {"approval_required": false, "conflict_with_rag": false}\n###TOOL_CALL### {"name": "GET_PENSION_PRODUCTS", "arguments": {}}'

    monkeypatch.setattr(chat_orch.pension_llm_service, "chat", fake_chat)

    tool_calls: list[str] = []

    def fake_execute_tool_call(
        *,
        tool_name: str,
        args: dict,
        client_id: int,
        db,
        pension_portfolio=None,
        force_max_exemption: bool = False,
        agent_reply: str | None = None,
        user_approved: bool = False,
        request_id: str | None = None,
    ) -> str:
        _ = (
            args,
            db,
            pension_portfolio,
            force_max_exemption,
            agent_reply,
            user_approved,
            request_id,
        )
        tool_calls.append(tool_name)
        return json.dumps(
            {
                "products": [
                    {
                        "category": "pension",
                        "fund_name": "פנסיה א",
                        "balance": 1000,
                    }
                ],
                "summary": "קיים מוצר פנסיוני אחד",
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(chat_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat",
        json={
            "client_id": 1,
            "messages": [{"role": "user", "content": "ניתוח תיק"}],
        },
    )

    assert response.status_code == 200
    body = response.json()["reply"]
    assert tool_calls == ["GET_PENSION_PRODUCTS"]
    assert "סיכום מהיר (הערכה ראשונית)" in body
    assert "מה אפשר לעשות עכשיו" in body
    assert "תוצאות בפועל במערכת" not in body


def test_stream_system_only_results_do_not_use_short_summary_framing(
    monkeypatch,
) -> None:
    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM should not be called for system results requests")

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

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
        return json.dumps(
            {
                "products": [
                    {"category": "pension", "fund_name": "פנסיה א", "balance": 1000}
                ]
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)
    monkeypatch.setattr(
        stream_orch,
        "load_latest_pension_portfolio_snapshot_models",
        lambda db, client_id: None,
    )

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [{"role": "user", "content": 'מה גובה סה"כ הקצבה כעת?'}],
        },
    )

    assert response.status_code == 200
    assert tool_calls == ["GET_PENSION_PRODUCTS"]
    body = response.text
    assert "תוצאות בפועל במערכת" in body
    assert "סיכום מהיר (הערכה ראשונית)" not in body


def test_stream_stop_after_tool_stays_cta_free(monkeypatch) -> None:
    call_count = {"n": 0}

    def fake_chat_stream(messages, client_id=None):
        call_count["n"] += 1
        if call_count["n"] == 1:
            yield '###TRANSPARENCY_LOG### {"test": true}\n###RISK_REVIEW### {"approval_required": false, "conflict_with_rag": false}\n###TOOL_CALL### {"name": "GET_PENSION_PRODUCTS", "arguments": {}}'
            return
        raise AssertionError("LLM should not be called again after stop-after-tool")

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

    tool_calls: list[str] = []

    def fake_execute_tool_call(
        *,
        tool_name: str,
        args: dict,
        client_id: int,
        db,
        pension_portfolio=None,
        force_max_exemption: bool = False,
        agent_reply: str | None = None,
        user_approved: bool = False,
        request_id: str | None = None,
    ) -> str:
        _ = (
            args,
            client_id,
            db,
            pension_portfolio,
            force_max_exemption,
            agent_reply,
            user_approved,
            request_id,
        )
        tool_calls.append(tool_name)
        return json.dumps({"success": True}, ensure_ascii=False)

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [{"role": "user", "content": "ניתוח ותיזמון פרישה"}],
        },
    )

    assert response.status_code == 200
    assert tool_calls == ["GET_PENSION_PRODUCTS"]
    body = response.text
    assert "להסבר מילולי בלי מספרים כתוב: הסבר במילים." in body
    assert "אם תרצה" not in body
    assert "?" not in body


def test_non_stream_numeric_provenance_path_does_not_fall_back_to_greeting(
    db_session, client, monkeypatch
) -> None:
    def fake_chat(messages, client_id=None):
        return "המספר הוא 12345"

    monkeypatch.setattr(chat_orch.pension_llm_service, "chat", fake_chat)

    req = ChatRequest(
        client_id=client.id,
        messages=[ChatMessage(role="user", content="שלום")],
        pension_portfolio=[],
    )

    resp = chat_orch.run_pension_chat(req, db_session)

    assert "12345" in resp.reply
    assert "שלום! אפשר לבקש ניתוח תיק או לבנות תכנית פרישה." not in resp.reply


def test_stage16_monthly_pension_routing_does_not_fall_back_to_default_qa(
    db_session, client, monkeypatch
) -> None:
    from app.schemas.llm_chat import ChatMessage, ChatRequest
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
            fund_name="MP-1",
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

    trace_id = "trace_stage16_monthly_pension_regression"
    set_current_trace_id(trace_id)
    try:
        db_session.info["trace_id"] = trace_id
    except Exception:
        pass

    req = ChatRequest(
        messages=[ChatMessage(role="user", content="קצבה חודשית")],
        client_id=int(client.id),
        pension_portfolio=None,
    )
    res = execute_agent_request(req, db_session)

    router_payload = capture.find_router_selected(trace_id)
    assert router_payload.get("capability_id") == "monthly_pension_summary_action_v1"
    assert router_payload.get("capability_id") != "default_qa_v1"


def test_termination_parser_planning_blocked_no_approval_or_pending(
    db_session, client, monkeypatch
) -> None:
    capture = _install_trace_capture(monkeypatch)
    trace_id = "trace_termination_parser_planning_blocked"
    user_text = "אני רוצה להבין אפשרויות של עזיבת עבודה"

    db_session.query(Scenario).filter(Scenario.client_id == client.id).filter(
        Scenario.scenario_name == "pending_approval"
    ).delete(synchronize_session=False)
    db_session.commit()

    decision = decide_stream_planning_execution_policy(user_text)
    assert is_process_termination_request(user_text) is False
    assert decision.planning_only is True
    assert decision.explicit_execution_intent is False

    body = "".join(
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

    assert "###UI_ACTION###" not in body
    pending = (
        db_session.query(Scenario)
        .filter(Scenario.client_id == client.id)
        .filter(Scenario.scenario_name == "pending_approval")
        .order_by(Scenario.created_at.desc())
        .first()
    )
    assert pending is None

    payload = capture.find_first_payload(
        "termination_parser_planning_blocked", trace_id
    )
    assert payload["planning_only"] is True
    assert payload["requested_execution"] is False
    assert payload["mapping_is_unambiguous"] is True


def test_termination_parser_requires_requested_execution_for_approval_creation(
    db_session, client, monkeypatch
) -> None:
    capture = _install_trace_capture(monkeypatch)
    trace_id = "trace_termination_parser_missing_requested_execution"
    user_text = "termination"

    db_session.query(Scenario).filter(Scenario.client_id == client.id).filter(
        Scenario.scenario_name == "pending_approval"
    ).delete(synchronize_session=False)
    db_session.commit()

    decision = decide_stream_planning_execution_policy(user_text)
    assert decision.planning_only is False
    assert decision.explicit_execution_intent is False

    body = "".join(
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

    assert "###UI_ACTION###" not in body
    pending = (
        db_session.query(Scenario)
        .filter(Scenario.client_id == client.id)
        .filter(Scenario.scenario_name == "pending_approval")
        .order_by(Scenario.created_at.desc())
        .first()
    )
    assert pending is None

    payload = capture.find_first_payload(
        "termination_parser_missing_requested_execution_blocked", trace_id
    )
    assert payload["planning_only"] is False
    assert payload["requested_execution"] is False
    assert payload["mapping_is_unambiguous"] is True


def test_termination_parser_ambiguous_mapping_no_unsafe_defaults(
    db_session, client, monkeypatch
) -> None:
    capture = _install_trace_capture(monkeypatch)
    trace_id = "trace_termination_parser_ambiguous_mapping"
    user_text = "הכל למשיכה ללא פטור"

    db_session.query(Scenario).filter(Scenario.client_id == client.id).filter(
        Scenario.scenario_name == "pending_approval"
    ).delete(synchronize_session=False)
    db_session.commit()

    decision = decide_stream_planning_execution_policy(user_text)
    assert decision.explicit_execution_intent is True
    assert decision.planning_only is False

    body = "".join(
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

    assert "###UI_ACTION###" not in body
    pending = (
        db_session.query(Scenario)
        .filter(Scenario.client_id == client.id)
        .filter(Scenario.scenario_name == "pending_approval")
        .order_by(Scenario.created_at.desc())
        .first()
    )
    assert pending is None

    payload = capture.find_first_payload(
        "termination_parser_ambiguous_mapping_blocked", trace_id
    )
    assert payload["requested_execution"] is True
    assert payload["mapping_is_unambiguous"] is False


def test_stage16_client_snapshot_routing_pattern_stays_stable(
    db_session, client, monkeypatch
) -> None:
    from app.schemas.llm_chat import ChatMessage, ChatRequest
    from app.services.agent_execution.execute_agent_request import execute_agent_request
    from app.services.llm_chat.capability_router.ssot_loader import load_capability_map
    from app.utils.trace_context import set_current_trace_id

    monkeypatch.setenv(
        "CAPABILITY_MAP_PATH", "tests/fixtures/stage16/capability_map_stage16.yaml"
    )
    load_capability_map.cache_clear()
    capture = _install_trace_capture(monkeypatch)

    trace_id = "trace_stage16_client_snapshot_regression"
    set_current_trace_id(trace_id)
    try:
        db_session.info["trace_id"] = trace_id
    except Exception:
        pass

    req = ChatRequest(
        messages=[ChatMessage(role="user", content="GET_CLIENT_SNAPSHOT")],
        client_id=int(client.id),
        pension_portfolio=None,
    )
    res = execute_agent_request(req, db_session)

    router_payload = capture.find_router_selected(trace_id)
    assert router_payload.get("capability_id") == "client_snapshot_action_v1"
    assert router_payload.get("capability_id") != "default_qa_v1"
    assert router_payload.get("tool_chain") == ["GET_CLIENT_SNAPSHOT"]
    computed_data = getattr(res, "computed_data", None)
    assert isinstance(computed_data, dict)
    assert set(computed_data.keys()) == {
        "success",
        "tool_name",
        "client_id",
        "total_items",
        "breakdown",
    }


@pytest.mark.parametrize(
    ("user_text", "expected_action", "forbidden_action"),
    [
        ("שלום", ACTION_GREETING_AND_MENU, ACTION_ANSWER_GENERAL_QUESTION),
        ("ניתוח ותיזמון פרישה", ACTION_PLAN_RETIREMENT, ACTION_GREETING_AND_MENU),
        (
            'מה גובה סה"כ הקצבה כעת?',
            ACTION_ANSWER_GENERAL_QUESTION,
            ACTION_GREETING_AND_MENU,
        ),
        ("קצבה חודשית", ACTION_ANSWER_GENERAL_QUESTION, ACTION_GREETING_AND_MENU),
        (
            "השווה בין שתי תכניות",
            ACTION_COMPARE_EXISTING_PLANS,
            ACTION_GREETING_AND_MENU,
        ),
    ],
)
def test_canonical_action_matrix_uses_expected_contracts(
    user_text: str,
    expected_action: str,
    forbidden_action: str,
) -> None:
    decision = select_canonical_action(user_text=user_text)

    assert decision.action == expected_action
    assert decision.action != forbidden_action


def test_monthly_pension_routing_marker_is_not_general_qa_default(
    db_session, client, monkeypatch
) -> None:
    from app.schemas.llm_chat import ChatMessage, ChatRequest
    from app.services.agent_execution.execute_agent_request import execute_agent_request
    from app.services.llm_chat.capability_router.ssot_loader import load_capability_map
    from app.utils.trace_context import set_current_trace_id

    monkeypatch.setenv(
        "CAPABILITY_MAP_PATH", "tests/fixtures/stage16/capability_map_stage16.yaml"
    )
    load_capability_map.cache_clear()
    capture = _install_trace_capture(monkeypatch)

    trace_id = "trace_stage16_matrix_monthly_pension"
    set_current_trace_id(trace_id)
    try:
        db_session.info["trace_id"] = trace_id
    except Exception:
        pass

    req = ChatRequest(
        messages=[ChatMessage(role="user", content="קצבה חודשית")],
        client_id=int(client.id),
        pension_portfolio=None,
    )
    _ = execute_agent_request(req, db_session)

    router_payload = capture.find_router_selected(trace_id)
    assert router_payload.get("capability_id") == "monthly_pension_summary_action_v1"
    assert router_payload.get("capability_id") != "default_qa_v1"
