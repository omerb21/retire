from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def test_stream_ack_understood_does_not_trigger_cashflow_error(monkeypatch) -> None:
    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for ack")

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

    def fake_execute_tool_call(*args, **kwargs) -> str:
        raise AssertionError("execute_tool_call must not be invoked for ack")

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    resp = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 960000104,
            "messages": [{"role": "user", "content": "הבנתי"}],
            "pension_portfolio": [],
        },
    )

    assert resp.status_code == 200
    assert "Tool Error" not in resp.text
    assert "יעד נטו" not in resp.text
    assert "כדי לחשב תזרים" not in resp.text
