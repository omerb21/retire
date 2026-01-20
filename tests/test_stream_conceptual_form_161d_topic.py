import json

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def test_stream_conceptual_form_161d_topic(monkeypatch) -> None:
    def fake_chat_stream(messages, client_id=None):
        yield "קיבוע זכויות הוא תהליך תכנוני בפרישה שמסדיר בחירות מול רשות המסים."

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 36,
            "messages": [
                {
                    "role": "user",
                    "content": "בקיבוע זכויות, מה התפקיד של טופס 161ד?",
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.text

    assert "###UI_ACTION###" not in body
    assert "/api/v1/fixation/" not in body

    assert ("161ד" in body) or ("טופס 161ד" in body)

    assert "₪" not in body
    assert "%" not in body

    assert "בתיק שלך" not in body
    assert "פיצויים" not in body


def test_stream_report_still_returns_ui_action(monkeypatch) -> None:
    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for report summary navigation")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    def fake_execute_tool_call(*args, **kwargs) -> str:
        raise AssertionError("No tool must be executed for report summary navigation")

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [{"role": "user", "content": "שלח דוח מסכם"}],
        },
    )

    assert response.status_code == 200
    body = response.text

    assert "###UI_ACTION###" in body
    assert "/clients/1/reports?auto_html=1" in body
