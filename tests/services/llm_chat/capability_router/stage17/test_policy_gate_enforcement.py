import hashlib
import json

import pytest


def _sha256_hex_utf8(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


@pytest.mark.parametrize(
    "tool_args,expect_fallback",
    [
        ({"a": 1, "b": "x"}, False),
        ({"x": object()}, True),
    ],
)
def test_stage17_policy_gate_blocked_args_hash_is_deterministic_and_payload_minimal(
    db_session, monkeypatch, tool_args, expect_fallback
) -> None:
    import app.services.agent_execution.tool_executor as tool_exec_mod
    import app.services.llm_chat.tool_execution as tool_execution_mod
    from app.schemas.llm_chat import ChatMessage, ChatRequest
    from app.services.llm_chat.capability_router.runtime_context import (
        RouterDecision,
        set_router_decision,
    )
    from app.utils.trace_context import set_current_trace_id

    monkeypatch.setenv("CAPABILITY_ROUTER_POLICY_GATE_ENABLED", "1")

    trace_id = "trace_stage17_policy_gate_hash"
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
        capability_map_version="17.0.0",
        router_normalization_version="1.0",
        normalized_text_hash="deadbeef",
    )
    set_router_decision(trace_id=trace_id, decision=decision)

    events: list[dict] = []

    def fake_log_trace_event(*, trace_id=None, event_type: str, payload=None, **kwargs):
        _ = kwargs
        events.append(
            {"trace_id": trace_id, "event_type": event_type, "payload": payload}
        )

    monkeypatch.setattr(tool_exec_mod, "log_trace_event", fake_log_trace_event)

    def fake_execute_tool_call(
        *, tool_name: str, args: dict, client_id: int, db, **kwargs
    ) -> str:
        _ = (tool_name, args, client_id, db, kwargs)
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
        tool_args=tool_args,
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

    blocked_events = [e for e in events if e["event_type"] == "policy_gate_blocked"]
    assert len(blocked_events) == 1

    payload = blocked_events[0]["payload"]
    assert isinstance(payload, dict)
    assert set(payload.keys()) == {"tool_id", "args_hash", "args_hash_fallback"}

    assert payload.get("tool_id") == "GET_PENSION_PRODUCTS"
    assert payload.get("args_hash_fallback") is bool(expect_fallback)

    if expect_fallback:
        assert payload.get("args_hash") == hashlib.sha256(b"").hexdigest()
    else:
        expected_json = json.dumps(
            tool_args, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        assert payload.get("args_hash") == _sha256_hex_utf8(expected_json)
