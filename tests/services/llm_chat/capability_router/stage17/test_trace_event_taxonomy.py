import json
import re


def test_stage17_trace_taxonomy_is_not_closed_list_for_policy_gate_blocked(
    db_session, monkeypatch
) -> None:
    import app.services.agent_execution.tool_executor as tool_exec_mod
    import app.services.agent_trace_logger as trace_logger_mod
    from app.schemas.llm_chat import ChatMessage, ChatRequest
    from app.services.llm_chat.capability_router.qa_claims_guard import (
        guard_qa_answer_payload,
    )
    from app.services.llm_chat.capability_router.router_facade import (
        ensure_router_decision,
    )
    from app.utils.trace_context import set_current_trace_id

    monkeypatch.setenv("CAPABILITY_ROUTER_POLICY_GATE_ENABLED", "1")

    trace_id = "trace_stage17_taxonomy_1"
    set_current_trace_id(trace_id)
    try:
        db_session.info["trace_id"] = trace_id
    except Exception:
        pass

    events: list[dict] = []

    def fake_log_trace_event(*, trace_id=None, event_type: str, payload=None, **kwargs):
        _ = kwargs
        events.append(
            {"trace_id": trace_id, "event_type": event_type, "payload": payload}
        )

    monkeypatch.setattr(tool_exec_mod, "log_trace_event", fake_log_trace_event)
    monkeypatch.setattr(trace_logger_mod, "log_trace_event", fake_log_trace_event)

    req = ChatRequest(
        messages=[ChatMessage(role="user", content="x")],
        client_id=1,
        pension_portfolio=None,
    )

    _ = ensure_router_decision(
        user_text="x", client_id=req.client_id, trace_id=trace_id
    )

    res = tool_exec_mod.execute_with_guard(
        request=req,
        db=db_session,
        tool_name="GET_PENSION_PRODUCTS",
        tool_call_id="tc1",
        tool_args={"a": 1},
        streaming=False,
        policy_decision=None,
        intent_type=None,
        pension_portfolio=None,
        force_max_exemption=False,
        agent_reply=None,
        user_approved=False,
        request_id="r1",
    )

    assert isinstance(res, dict)
    assert res.get("status") == "policy_blocked"

    monkeypatch.setenv("CAPABILITY_ROUTER_POLICY_GATE_ENABLED", "0")

    _ = tool_exec_mod.execute_with_guard(
        request=req,
        db=db_session,
        tool_name="GET_SYSTEM_NUMERIC_CONSTANTS",
        tool_call_id="tc2",
        tool_args={},
        streaming=False,
        policy_decision=None,
        intent_type=None,
        pension_portfolio=None,
        force_max_exemption=False,
        agent_reply=None,
        user_approved=True,
        request_id="r2",
    )

    _ = guard_qa_answer_payload(
        qa_answer_payload={
            "mode": "QA",
            "answer_blocks": [{"type": "explanation", "text": "it is 12"}],
        },
        trace_id=trace_id,
        client_id=req.client_id,
        detected_capability_id="default_qa_v1",
    )

    event_types = [e.get("event_type") for e in events]

    assert "policy_gate_blocked" in event_types
    assert "router_selected" in event_types

    router_events = [e for e in events if e.get("event_type") == "router_selected"]
    assert len(router_events) == 1

    router_payload = router_events[0].get("payload")
    assert isinstance(router_payload, dict)

    assert set(router_payload.keys()) == {
        "capability_id",
        "tool_chain",
        "output_schema_id",
        "capability_map_version",
        "router_normalization_version",
        "normalized_text_hash",
    }

    for forbidden_key in ("user_text", "raw_text", "normalized_text", "messages"):
        assert forbidden_key not in router_payload

    assert isinstance(router_payload.get("normalized_text_hash"), str)
    assert (
        re.fullmatch(r"[0-9a-f]{64}", router_payload["normalized_text_hash"])
        is not None
    )

    assert "predicate_eval" in event_types

    pred_events = [e for e in events if e.get("event_type") == "predicate_eval"]
    assert pred_events

    for pe in pred_events:
        pp = pe.get("payload")
        assert isinstance(pp, dict)
        assert set(pp.keys()) == {"rule_id", "outcome", "params_hash"}
        assert isinstance(pp.get("rule_id"), str) and pp.get("rule_id")
        assert pp.get("outcome") in {True, False}
        assert isinstance(pp.get("params_hash"), str)
        assert re.fullmatch(r"[0-9a-f]{64}", pp["params_hash"]) is not None

        for forbidden_key in (
            "user_text",
            "raw_text",
            "normalized_text",
            "messages",
            "params",
        ):
            assert forbidden_key not in pp

    assert "tool_started" in event_types
    assert "tool_finished" in event_types

    started_events = [e for e in events if e.get("event_type") == "tool_started"]
    assert started_events
    for se in started_events:
        sp = se.get("payload")
        assert isinstance(sp, dict)
        assert set(sp.keys()) == {"tool_id", "args_hash"}
        assert isinstance(sp.get("tool_id"), str) and sp.get("tool_id")
        assert isinstance(sp.get("args_hash"), str)
        assert re.fullmatch(r"[0-9a-f]{64}", sp["args_hash"]) is not None

    finished_events = [e for e in events if e.get("event_type") == "tool_finished"]
    assert finished_events
    for fe in finished_events:
        fp = fe.get("payload")
        assert isinstance(fp, dict)
        assert set(fp.keys()) in (
            {"tool_id", "success", "duration_ms"},
            {"tool_id", "success", "duration_ms", "error_type"},
        )
        assert isinstance(fp.get("tool_id"), str) and fp.get("tool_id")
        assert fp.get("success") in {True, False}
        assert isinstance(fp.get("duration_ms"), int)
        if "error_type" in fp:
            assert isinstance(fp.get("error_type"), str) and fp.get("error_type")

    assert "schema_rendered" in event_types

    schema_events = [e for e in events if e.get("event_type") == "schema_rendered"]
    assert schema_events
    for se in schema_events:
        sp = se.get("payload")
        assert isinstance(sp, dict)
        assert set(sp.keys()) == {"output_schema_id", "result_keys"}
        assert isinstance(sp.get("output_schema_id"), str) and sp.get(
            "output_schema_id"
        )
        assert isinstance(sp.get("result_keys"), list)
        for k in sp.get("result_keys"):
            assert isinstance(k, str)

    allowed_extra_events = {"pii_redaction_failed", "budget_guard_unenforceable"}
    _ = allowed_extra_events

    serialized = json.dumps(events, ensure_ascii=False)
    assert "tool_args" not in serialized
    assert "arguments" not in serialized
