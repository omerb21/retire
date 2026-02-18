from __future__ import annotations

from typing import Any

from app.schemas.llm_chat import ChatMessage, ChatRequest
from app.services.agent_execution import execute_agent_request as core_mod


def test_stage8_trace_baseline_non_stream_event_order(monkeypatch, db_session):
    events: list[tuple[str, Any]] = []

    def fake_log_trace_event(*, event_type: str, payload=None, **kwargs):
        events.append((event_type, payload))

    monkeypatch.setattr(core_mod, "log_trace_event", fake_log_trace_event)

    req = ChatRequest(messages=[ChatMessage(role="user", content="monthly_pension")], client_id=1)
    core_mod.execute_agent_request(req, db_session)

    types = [t for (t, _p) in events]

    assert "user_input" in types
    assert "intent_detected" in types
    assert "policy_decision" in types
    assert "execution_mode" in types
    assert "final_response" in types

    assert types.index("user_input") < types.index("intent_detected")
    assert types.index("policy_decision") < types.index("execution_mode")
    assert types.index("execution_mode") < types.index("final_response")
