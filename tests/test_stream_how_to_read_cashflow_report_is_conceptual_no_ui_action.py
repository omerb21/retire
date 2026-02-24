from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def test_stream_how_to_read_cashflow_report_is_conceptual_no_ui_action(
    monkeypatch,
) -> None:
    def fake_chat_stream(messages, client_id=None):
        yield "בתיק שלך"

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

    def fake_execute_tool_call(*args, **kwargs) -> str:
        raise AssertionError(
            "execute_tool_call must not be invoked for conceptual report-reading questions"
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

    assert body.strip()
    assert "###UI_ACTION###" not in body
    assert "🔧" not in body
    assert "שאלה מושגית" in body
