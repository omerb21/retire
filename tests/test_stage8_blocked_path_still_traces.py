from __future__ import annotations

from typing import Any

from app.schemas.llm_chat import ChatMessage, ChatRequest
from app.services.agent_execution import execute_agent_request as core_mod
from app.services.agent_execution import tool_executor as tool_exec_mod


def test_stage8_blocked_path_still_traces_validation_error_and_tool_result_and_final_response(
    monkeypatch, db_session
):
    events: list[tuple[str, Any]] = []

    def fake_log_trace_event(*, event_type: str, payload=None, **kwargs):
        events.append((event_type, payload))

    monkeypatch.setattr(core_mod, "log_trace_event", fake_log_trace_event)
    monkeypatch.setattr(tool_exec_mod, "log_trace_event", fake_log_trace_event)

    # NO_TOOLS intent -> policy.tools_allowed=False -> guard blocks tool
    msg = "GET_CLIENT_SNAPSHOT בלי כלים"
    req = ChatRequest(messages=[ChatMessage(role="user", content=msg)], client_id=1)
    core_mod.execute_agent_request(req, db_session)

    types = [t for (t, _p) in events]

    assert "tool_call" in types
    assert "validation_error" in types
    assert "tool_result" in types
    assert "final_response" in types

    tool_result_payloads = [p for (t, p) in events if t == "tool_result"]
    assert tool_result_payloads
    assert tool_result_payloads[0].get("status") in {
        "blocked_by_guard",
        "blocked_by_contract",
    }
