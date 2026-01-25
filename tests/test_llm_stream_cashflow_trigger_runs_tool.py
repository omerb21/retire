from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def test_cashflow_trigger_runs_tool(monkeypatch) -> None:
    executed = {"count": 0, "tool_name": None}

    from app.services.llm_chat.chat_stream_orchestration_parts.orchestrator_impl_parts import (
        stream_loop,
    )

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
        raise AssertionError("Tool must not be executed when cashflow target is missing")

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

    assert executed["count"] == 0

    assert "🔧" not in body
    assert "פלט כלי" not in body
    assert "Tool Error" not in body
    assert "יעד נטו" in body
    assert "יעד ברוטו" in body
    assert "יעד נטו: <מספר>" in body
    assert "יעד ברוטו: <מספר>" in body
    assert "יעד נטו: 28000" in body
    assert "יעד ברוטו: 31000" in body
    assert "15,000" not in body
    assert "הפקתי את תוצאות הניתוח מהמערכת" not in body

    assert not body.lstrip().startswith("**דוח תזרים לפרישה")
