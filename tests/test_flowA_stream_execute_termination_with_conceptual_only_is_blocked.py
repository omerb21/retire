from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def test_flowA_stream_execute_termination_with_conceptual_only_is_blocked(
    monkeypatch,
) -> None:
    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for conceptual-only hard stop")

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

    def fake_execute_tool_call(*args, **kwargs):
        raise AssertionError(
            "execute_tool_call must not be invoked for conceptual-only hard stop"
        )

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    resp = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [
                {
                    "role": "user",
                    "content": "בצע עזיבת עבודה עכשיו אבל אני מבקש להסביר עקרון בלבד ואל תבצע בפועל",
                }
            ],
            "pension_portfolio": [],
        },
    )

    assert resp.status_code == 200
    body = resp.text
    assert "###UI_ACTION###" not in body
    assert "approval_request" not in body
    assert "🔧" not in body
    assert "סיכום ביצוע" not in body
    assert "בוצע" not in body
