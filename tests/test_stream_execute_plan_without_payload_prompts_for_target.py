from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def test_stream_execute_plan_without_payload_prompts_for_target(monkeypatch) -> None:
    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for deterministic execute-plan prompt")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 888001,
            "messages": [{"role": "user", "content": "בצע את התכנית בפועל"}],
            "pension_portfolio": [],
        },
    )

    assert response.status_code == 200
    body = response.text
    assert "כדי לבצע תכנית בפועל צריך קודם לבנות תכנית יעד עם מספר" in body
    assert "כתוב: יעד נטו: <מספר>." in body
    assert "לדוגמה: יעד נטו: 28000" in body
    assert "###UI_ACTION###" not in body
    assert "###TOOL_CALL###" not in body
    assert "🔧" not in body
