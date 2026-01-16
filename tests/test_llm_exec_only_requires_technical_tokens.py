from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def test_llm_exec_only_requires_technical_tokens(monkeypatch) -> None:
    def fake_chat_stream(messages, client_id=None):
        system_text = (getattr(messages[0], "content", "") or "") if messages else ""

        if "עורך-שכתוב" in system_text:
            yield "פלט שגוי"
            return

        yield (
            "מטרה: להפיק הנחיות טכניות למודל המתכנת\n"
            "הנחיות למודל המתכנת:\n"
            "א. בצע שינוי\n"
            "קריטריון הצלחה:\n"
            "- תקין\n"
            "סטטוס: SUCCESS"
        )

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        headers={"X-Executor-Only": "1"},
        json={
            "client_id": 1,
            "messages": [
                {"role": "user", "content": "כתוב הנחיות טכניות למודל המתכנת מה לבצע"}
            ],
        },
    )

    assert response.status_code == 200
    body = response.text

    assert "סטטוס: SUCCESS" in body
    assert "curl.exe" in body
    assert "pytest" in body
    assert "git" in body
    assert ("app/" in body) or ("tests/" in body) or ("Dockerfile" in body)
