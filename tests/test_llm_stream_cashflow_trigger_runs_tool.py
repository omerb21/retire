from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def test_cashflow_trigger_runs_tool(monkeypatch) -> None:
    from app.services.llm_chat.chat_stream_orchestration_parts.orchestrator_impl_parts import (
        stream_loop,
    )

    executed = {"count": 0, "tool_name": None}

    def fake_execute_tool_call(
        tool_name: str,
        tool_args: dict,
        client_id: int,
        db,
        pension_portfolio=None,
        force_max_exemption: bool = False,
        user_approved: bool = True,
        request_id: str | None = None,
    ) -> str:
        executed["count"] += 1
        executed["tool_name"] = tool_name
        assert tool_name == "RUN_RETIREMENT_CASHFLOW_ANALYSIS"
        return "FAKE_TOOL_RESULT"

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be used for cashflow calc requests")

    monkeypatch.setattr(stream_loop, "_execute_tool_call", fake_execute_tool_call)
    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "pension_portfolio": [],
            "messages": [{"role": "user", "content": "תחשב לי תזרים פרישה"}],
        },
    )

    assert response.status_code == 200
    body = response.text

    assert executed["count"] == 1

    assert ("🔧" in body) or ("פלט כלי" in body)
    assert (
        "הפקתי את תוצאות הניתוח מהמערכת. להסבר מילולי בלי מספרים כתוב: הסבר במילים." in body
    )

    assert not body.lstrip().startswith("**דוח תזרים לפרישה")
