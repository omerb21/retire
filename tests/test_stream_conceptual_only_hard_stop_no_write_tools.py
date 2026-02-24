from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
import app.services.llm_chat.chat_stream_orchestration_parts.orchestrator_impl_parts.stream_loop as stream_loop
from app.main import app


def test_stream_conceptual_only_request_does_not_execute_write_tools(
    monkeypatch,
) -> None:
    def fake_chat_stream(messages, client_id=None):
        yield "זו תשובה מושגית בלבד."

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

    def fake_execute_tool_call(*args, **kwargs) -> str:
        raise AssertionError(
            "execute_tool_call must not be invoked for conceptual-only requests"
        )

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)
    monkeypatch.setattr(stream_loop, "_execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    resp = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [
                {
                    "role": "user",
                    "content": "פיצויים - עיקרון בלבד, רק להסביר בלי לבצע שום דבר",
                }
            ],
            "pension_portfolio": [],
        },
    )
    assert resp.status_code == 200
    body = resp.text
    assert "###UI_ACTION###" not in body
    assert "###TOOL_CALL###" not in body
    assert "🔧" not in body
