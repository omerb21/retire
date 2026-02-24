from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def test_stream_conceptual_how_to_read_cashflow_report_structured_steps(
    monkeypatch,
) -> None:
    def fake_chat_stream(messages, client_id=None):
        injected = "\n\n".join(
            str(getattr(m, "content", ""))
            for m in (messages or [])
            if getattr(m, "role", None) == "system"
        )
        assert "## how_to_read_cashflow_report_steps.md" in injected
        assert "איך לקרוא דוח תזרים" in injected
        assert "כלל קשיח לשאלות מושגיות" in injected

        yield (
            "איך לקרוא דוח תזרים\n"
            "א. התחלה: ודא טווח זמן ונקודת מוצא\n"
            "ב. מקורות: זהה הכנסות ומקור נתונים\n"
            "ג. מס: בדוק היכן מוצגים מס וניכויים\n"
            "ד. נטו: ודא מה נגזר אחרי מס\n"
        )

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

    def fake_execute_tool_call(*args, **kwargs) -> str:
        raise AssertionError(
            "execute_tool_call must not be invoked for conceptual questions"
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
                    "content": "איך לקרוא דוח תזרים בצורה נכונה",
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.text

    assert "###UI_ACTION###" not in body
    assert "🔧" not in body

    assert "דוח תזרים" in body

    letter_steps = sum(1 for token in ("א.", "ב.", "ג.", "ד.") if token in body)
    numbered_steps = sum(1 for token in ("1.", "2.", "3.", "4.") if token in body)
    assert (letter_steps >= 4) or (numbered_steps >= 4)
