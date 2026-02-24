from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def test_stream_conceptual_form_161d_always_mentions_161d(monkeypatch) -> None:
    def fake_chat_stream(messages, client_id=None):
        yield "שדה: זיהוי במערכת"

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

    def fake_execute_tool_call(*args, **kwargs) -> str:
        raise AssertionError(
            "execute_tool_call must not be invoked for conceptual 161ד questions"
        )

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [
                {"role": "user", "content": "בקיבוע זכויות מה התפקיד של טופס 161ד"}
            ],
        },
    )

    assert response.status_code == 200
    body = response.text

    assert "🔧" not in body
    assert "###UI_ACTION###" not in body
    assert "161ד" in body
