import json
import os
from typing import Any

import pytest


def test_stage15_router_selected_emitted_once_and_no_raw_text(monkeypatch) -> None:
    import app.services.llm_chat.orchestration_core.orchestrate as orch_mod
    from app.services.llm_chat.capability_router.ssot_loader import \
        load_capability_map
    from app.services.llm_chat.orchestration_core.core_types import (
        OrchestrationDeps, OrchestrationInput)

    monkeypatch.setenv(
        "CAPABILITY_MAP_PATH", "tests/fixtures/capability_map_minimal.yaml"
    )
    load_capability_map.cache_clear()

    trace_id = "trace_stage15_router_selected_1"
    user_text = "please snapshot"

    deps = OrchestrationDeps(
        llm_generate=lambda _messages, _client_id=None: "",
        tool_defaults=lambda _tool_name: {},
    )

    input1 = OrchestrationInput(
        user_text=user_text,
        client_id=1,
        session_id=None,
        conversation_id=None,
        trace_id=trace_id,
        feature_flags={},
        request_meta=None,
        state_snapshot={},
        last_tool_result=None,
    )

    _d1, trace_specs1 = orch_mod.orchestrate(input1, deps)

    router_events1 = [s for s in trace_specs1 if s.event_type == "router_selected"]
    assert len(router_events1) == 1

    payload1 = router_events1[0].payload
    assert isinstance(payload1, dict)
    assert payload1.get("normalized_text_hash")
    assert "normalized_text" not in payload1
    assert "user_text" not in payload1

    serialized = json.dumps(payload1, ensure_ascii=False)
    assert user_text not in serialized

    input2 = OrchestrationInput(
        user_text=user_text,
        client_id=1,
        session_id=None,
        conversation_id=None,
        trace_id=trace_id,
        feature_flags={},
        request_meta=None,
        state_snapshot={},
        last_tool_result=None,
    )

    _d2, trace_specs2 = orch_mod.orchestrate(input2, deps)
    router_events2 = [s for s in trace_specs2 if s.event_type == "router_selected"]
    assert len(router_events2) == 0


def test_stage15_policy_gate_blocked_emits_trace_and_returns_partial_result(
    db_session, monkeypatch
) -> None:
    import app.services.agent_execution.tool_executor as tool_exec_mod
    import app.services.llm_chat.tool_execution as tool_execution_mod
    from app.schemas.llm_chat import ChatMessage, ChatRequest
    from app.services.llm_chat.capability_router.runtime_context import (
        RouterDecision, set_router_decision)
    from app.utils.trace_context import set_current_trace_id

    gate_enabled = (
        os.getenv("CAPABILITY_ROUTER_POLICY_GATE_ENABLED") or ""
    ).strip() == "1"

    trace_id = "trace_stage15_policy_gate_1"
    set_current_trace_id(trace_id)
    try:
        db_session.info["trace_id"] = trace_id
    except Exception:
        pass

    decision = RouterDecision(
        capability_id="client_snapshot_action_v1",
        mode="ACTION",
        tool_chain=["tool.client_snapshot_v1"],
        output_schema_id="action_ok_v1",
        capability_map_version="15.5.0",
        router_normalization_version="1.0",
        normalized_text_hash="deadbeef",
    )
    set_router_decision(trace_id=trace_id, decision=decision)

    events: list[dict[str, Any]] = []

    def fake_log_trace_event(*, trace_id=None, event_type: str, payload=None, **kwargs):
        _ = kwargs
        events.append(
            {"trace_id": trace_id, "event_type": event_type, "payload": payload}
        )

    monkeypatch.setattr(tool_exec_mod, "log_trace_event", fake_log_trace_event)

    def fake_execute_tool_call(
        *, tool_name: str, args: dict, client_id: int, db, **kwargs
    ) -> str:
        _ = (args, client_id, db, kwargs)
        return json.dumps({"success": True, "tool_name": tool_name}, ensure_ascii=False)

    monkeypatch.setattr(tool_execution_mod, "execute_tool_call", fake_execute_tool_call)

    req = ChatRequest(
        messages=[ChatMessage(role="user", content="x")],
        client_id=1,
        pension_portfolio=None,
    )

    res = tool_exec_mod.execute_with_guard(
        request=req,
        db=db_session,
        tool_name="GET_PENSION_PRODUCTS",
        tool_call_id="tc1",
        tool_args={"secret": "should_not_log"},
        streaming=False,
        policy_decision=None,
        intent_type=None,
        pension_portfolio=None,
        force_max_exemption=False,
        agent_reply=None,
        user_approved=False,
        request_id="r1",
    )

    blocked_events = [e for e in events if e["event_type"] == "policy_gate_blocked"]

    if gate_enabled:
        assert isinstance(res, dict)
        assert res["status"] == "policy_blocked"
        assert res["detected_capability_id"] == "client_snapshot_action_v1"
        assert res["policy_reasons"] == ["tool_not_in_allowlist"]

        assert len(blocked_events) == 1
        payload = blocked_events[0]["payload"]
        assert isinstance(payload, dict)
        assert set(payload.keys()) == {"tool_id", "args_hash", "args_hash_fallback"}
        assert payload.get("tool_id") == "GET_PENSION_PRODUCTS"
        assert isinstance(payload.get("args_hash"), str) and payload.get("args_hash")
        assert payload.get("args_hash_fallback") in {True, False}
    else:
        parsed = json.loads(res)
        assert parsed.get("success") is True
        assert parsed.get("tool_name") == "GET_PENSION_PRODUCTS"

        assert blocked_events == []


def test_stage15_qa_claims_guard_blocks_and_passes(monkeypatch) -> None:
    import app.services.agent_trace_logger as trace_logger_mod
    from app.services.llm_chat.capability_router.qa_claims_guard import \
        guard_qa_answer_payload

    events: list[dict[str, Any]] = []

    def fake_log_trace_event(*, trace_id=None, event_type: str, payload=None, **kwargs):
        _ = kwargs
        events.append(
            {"trace_id": trace_id, "event_type": event_type, "payload": payload}
        )

    monkeypatch.setattr(trace_logger_mod, "log_trace_event", fake_log_trace_event)

    blocked = guard_qa_answer_payload(
        qa_answer_payload={
            "mode": "QA",
            "answer_blocks": [{"type": "explanation", "text": "it is 12"}],
        },
        trace_id="tqa1",
        client_id=1,
        detected_capability_id="default_qa_v1",
    )
    assert blocked["status"] == "policy_blocked"
    assert blocked["policy_reasons"] == ["anchors_missing"]

    blocked2 = guard_qa_answer_payload(
        qa_answer_payload={
            "mode": "QA",
            "answer_blocks": [{"type": "explanation", "text": "Guaranteed results."}],
        },
        trace_id="tqa2",
        client_id=1,
        detected_capability_id="default_qa_v1",
    )
    assert blocked2["status"] == "policy_blocked"
    assert "forbidden_claims" in blocked2["policy_reasons"]

    ok = guard_qa_answer_payload(
        qa_answer_payload={
            "mode": "QA",
            "answer_blocks": [
                {"type": "explanation", "text": "No digits here."},
            ],
        },
        trace_id="tqa3",
        client_id=1,
        detected_capability_id="default_qa_v1",
    )
    assert ok["mode"] == "QA"
    assert isinstance(ok.get("answer_blocks"), list)
    assert len(ok["answer_blocks"]) >= 1

    qa_blocked_events = [e for e in events if e["event_type"] == "qa_claims_blocked"]
    assert len(qa_blocked_events) >= 2
    for e in qa_blocked_events:
        payload = e["payload"]
        assert isinstance(payload, dict)
        assert "policy_reasons" in payload
        serialized = json.dumps(payload, ensure_ascii=False)
        assert "12" not in serialized
        assert "Guaranteed" not in serialized
