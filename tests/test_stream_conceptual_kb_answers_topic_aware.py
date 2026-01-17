from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def test_stream_conceptual_kb_answer_topic_aware_fallback(monkeypatch) -> None:
    def fake_chat_stream(messages, client_id=None):
        yield "בתיק שלך קיימים רכיבים שדורשים בדיקת מקורות.\nקיבלתי. אפשר להמשיך"

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [{"role": "user", "content": "מה המשמעות של קיבוע זכויות"}],
        },
    )

    assert response.status_code == 200
    body = response.text

    assert "###TOOL_CALL###" not in body
    assert "🔧" not in body

    assert ("קיבוע זכויות" in body) or ("161ד" in body)
    assert "קצבה היא הכנסה חודשית" not in body


def test_stream_conceptual_kb_answer_keeps_kitzba_vs_hon_fallback(monkeypatch) -> None:
    def fake_chat_stream(messages, client_id=None):
        yield "בתיק שלך קיימים רכיבים שדורשים בדיקת מקורות.\nקיבלתי. אפשר להמשיך"

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [
                {
                    "role": "user",
                    "content": "מה ההבדל העקרוני בין קצבה להון",
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.text

    assert "###TOOL_CALL###" not in body
    assert "🔧" not in body

    assert "קצבה היא הכנסה חודשית" in body
