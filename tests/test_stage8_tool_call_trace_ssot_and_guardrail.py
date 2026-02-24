from __future__ import annotations

import pathlib
from typing import Any

from app.schemas.llm_chat import ChatMessage, ChatRequest
from app.services.agent_execution import execute_agent_request as core_mod
from app.services.agent_execution import tool_executor as tool_exec_mod


def test_stage8_tool_call_trace_ssot(monkeypatch, db_session):
    events: list[tuple[str, Any]] = []

    def fake_log_trace_event(*, event_type: str, payload=None, **kwargs):
        events.append((event_type, payload))

    monkeypatch.setattr(core_mod, "log_trace_event", fake_log_trace_event)
    monkeypatch.setattr(tool_exec_mod, "log_trace_event", fake_log_trace_event)

    req = ChatRequest(
        messages=[ChatMessage(role="user", content="GET_CLIENT_SNAPSHOT")], client_id=1
    )
    core_mod.execute_agent_request(req, db_session)

    types = [t for (t, _p) in events]
    assert "tool_call" in types
    assert "tool_result" in types
    assert types.index("tool_call") < types.index("tool_result")

    tool_call_payloads = [p for (t, p) in events if t == "tool_call"]
    assert tool_call_payloads
    assert tool_call_payloads[0].get("tool_name") == "GET_CLIENT_SNAPSHOT"


def test_stage8_guardrail_no_raw_execute_tool_call_imports_outside_ssot():
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    app_dir = repo_root / "app"

    bad: list[str] = []
    for p in app_dir.rglob("*.py"):
        # allow inside the SSOT executor only
        if p.name == "tool_executor.py" and "agent_execution" in str(p):
            continue

        txt = p.read_text(encoding="utf-8", errors="ignore")
        if "from app.services.llm_chat.tool_execution import execute_tool_call" in txt:
            bad.append(str(p))

    assert bad == []
