from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def test_stream_advice_tax_no_cashflow(monkeypatch) -> None:
    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for tax optimization advice")

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

    def fake_execute_tool_call(*args, **kwargs) -> str:
        raise AssertionError(
            "execute_tool_call must not be invoked for tax optimization advice"
        )

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [
                {"role": "user", "content": "ייעוץ תכנון מס בפרישה - איך לשלם פחות מס"}
            ],
        },
    )

    assert response.status_code == 200
    body = response.text

    assert "🔧" not in body
    assert "###UI_ACTION###" not in body
    assert "כדי לענות על זה בצורה נכונה נדרש חישוב מדויק" not in body

    assert "כותרת: תכנון מס בפרישה – מיפוי ראשוני" in body
    assert "מקורות מס עיקריים בפרישה" in body
    assert "איפה לרוב נשרף כסף" in body
    assert "מה דורש חישוב מדויק" in body
    assert "אילו החלטות בלתי הפיכות" in body
