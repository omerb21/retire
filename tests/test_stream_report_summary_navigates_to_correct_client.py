from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def test_stream_report_summary_navigates_to_correct_client(monkeypatch) -> None:
    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for report summary navigation")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    def fake_execute_tool_call(*args, **kwargs):
        raise AssertionError("No tool must be executed for report summary navigation")

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 424242,
            "messages": [{"role": "user", "content": "פתח דוח מסכם"}],
            "pension_portfolio": [],
        },
    )

    assert response.status_code == 200
    body = response.text
    assert "###UI_ACTION###" in body
    assert "/clients/424242/reports?auto_html=1" in body
    assert '"type": "open_url"' in body
    assert '"type": "navigate"' not in body
