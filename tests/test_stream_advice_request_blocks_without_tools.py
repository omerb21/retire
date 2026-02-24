from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def test_stream_advice_request_blocks_without_tools(monkeypatch) -> None:
    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for advice/what-to-do requests")

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

    def fake_execute_tool_call(*args, **kwargs) -> str:
        raise AssertionError(
            "Tools must not be executed when advice request is missing cashflow inputs"
        )

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [
                {
                    "role": "user",
                    "content": "אין לי זמן. תן תשובה קצרה מה הכי נכון לעשות עם הפיצויים",
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.text

    assert "###UI_ACTION###" not in body
    assert "🔧" not in body
    assert "כדי לענות על זה בצורה נכונה" in body
