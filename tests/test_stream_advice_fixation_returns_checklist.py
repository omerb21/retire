from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def test_stream_advice_fixation_returns_checklist(monkeypatch) -> None:
    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for fixation advice")

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

    def fake_execute_tool_call(*args, **kwargs) -> str:
        raise AssertionError(
            "execute_tool_call must not be invoked for fixation advice"
        )

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [
                {"role": "user", "content": "אני צריך ייעוץ על קיבוע זכויות וטופס 161ד"}
            ],
        },
    )

    assert response.status_code == 200
    body = response.text

    assert "🔧" not in body
    assert "###UI_ACTION###" not in body
    assert "כדי לענות על זה בצורה נכונה נדרש חישוב מדויק" not in body

    assert "כותרת: בדיקת קיבוע זכויות – שלב אבחון" in body
    assert "בדיקות נדרשות:" in body
    assert "פעולה הבאה:" in body
