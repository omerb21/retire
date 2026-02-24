from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def test_stream_advice_investment_risk_no_tools(monkeypatch) -> None:
    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for investment risk advice")

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

    def fake_execute_tool_call(*args, **kwargs) -> str:
        raise AssertionError(
            "execute_tool_call must not be invoked for investment risk advice"
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
                    "content": "אני צריך ייעוץ: מסלול השקעה וסיכון בגיל פרישה",
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.text

    assert "🔧" not in body
    assert "###UI_ACTION###" not in body
    assert "כדי לענות על זה בצורה נכונה נדרש חישוב מדויק" not in body

    assert "כותרת: סיכון השקעה בגיל פרישה" in body
    assert "איך סיכון משפיע בגיל פרישה" in body
    assert "ההבדל בין תנודתיות לתשואה" in body
    assert 'למה אין מסלול "נכון לכולם"' in body
    assert "מתי כן צריך חישוב" in body
    assert "בלי מספרים. בלי המלצה חד משמעית." in body
