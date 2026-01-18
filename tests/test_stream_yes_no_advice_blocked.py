from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def test_stream_yes_no_advice_blocked_first_case(monkeypatch) -> None:
    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for yes/no advice requests")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    def fake_execute_tool_call(*args, **kwargs) -> str:
        return "OK"

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [
                {
                    "role": "user",
                    "content": "תגיד רק כן או לא: למשוך פיצויים זה נכון",
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.text

    assert body.strip()
    assert "כדי לענות על זה בצורה נכונה נדרש חישוב מדויק במערכת הפרישה" not in body
    assert "🔧" in body
    assert "כותרת: סיכום החלטה לגבי פיצויים" in body
    assert "כותרת: הבהרה לפני ייעוץ" not in body
    assert "###UI_ACTION###" not in body


def test_stream_yes_no_advice_blocked_second_case(monkeypatch) -> None:
    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for yes/no advice requests")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    def fake_execute_tool_call(*args, **kwargs) -> str:
        raise AssertionError("execute_tool_call must not be invoked for unknown-domain advice")

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [
                {
                    "role": "user",
                    "content": "רק מילה אחת: נכון או לא נכון להשאיר הכל בקצבה",
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.text

    assert body.strip()
    assert "כדי לענות על זה בצורה נכונה נדרש חישוב מדויק במערכת הפרישה" not in body
    assert "🔧" not in body
    assert "כותרת: הבהרה לפני ייעוץ" in body
    assert "###UI_ACTION###" not in body
