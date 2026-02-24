from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def test_no_tools_stream_no_questions_regression(monkeypatch) -> None:
    def fake_chat_stream(messages, client_id=None):
        yield "קיבלתי. האם תרצה שאמשיך? בחר משהו."

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [{"role": "user", "content": "אל תפעיל כלים. ענה רק במילים."}],
        },
    )

    assert response.status_code == 200
    body = response.text
    assert "?" not in body
    assert "האם" not in body
    assert "תרצה" not in body
    assert "בחר" not in body
