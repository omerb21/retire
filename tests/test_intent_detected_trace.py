from __future__ import annotations

from typing import Any

from app.schemas.llm_chat import ChatMessage, ChatRequest
from app.services.agent_execution import execute_agent_request as core_mod


def _build_req(msg: str) -> ChatRequest:
    return ChatRequest(messages=[ChatMessage(role="user", content=msg)], client_id=1)


def test_non_stream_emits_intent_detected_before_policy_decision(monkeypatch, db_session):
    events: list[tuple[str, Any]] = []

    def fake_log_trace_event(*, event_type: str, payload=None, **kwargs):
        events.append((event_type, payload))

    monkeypatch.setattr(core_mod, "log_trace_event", fake_log_trace_event)

    req = _build_req("monthly_pension")
    core_mod.execute_agent_request(req, db_session)

    types = [t for (t, _p) in events]
    assert "intent_detected" in types
    assert "policy_decision" in types
    assert types.index("intent_detected") < types.index("policy_decision")


def test_stream_emits_intent_detected_before_policy_decision(monkeypatch, db_session):
    events: list[tuple[str, Any]] = []

    def fake_log_trace_event(*, event_type: str, payload=None, **kwargs):
        events.append((event_type, payload))

    monkeypatch.setattr(core_mod, "log_trace_event", fake_log_trace_event)

    req = _build_req("monthly_pension")
    core_mod.execute_agent_request_stream(req, db_session)

    types = [t for (t, _p) in events]
    assert "intent_detected" in types
    assert "policy_decision" in types
    assert types.index("intent_detected") < types.index("policy_decision")
