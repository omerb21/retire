from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
import app.services.llm_chat.chat_stream_orchestration_parts.orchestrator_impl_parts.stream_loop as stream_loop
from app.main import app


def test_stream_injects_retirement_kb_system_message(monkeypatch) -> None:
    captured = {"messages": None}

    monkeypatch.setattr(
        stream_loop, "get_retirement_kb_for_stream", lambda: "KB_TEST_MARKER"
    )

    def fake_chat_stream(messages, client_id=None):
        captured["messages"] = messages
        yield "תשובה קצרה"

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [{"role": "user", "content": "אל תפעיל כלים. ענה רק במילים."}],
        },
    )

    assert response.status_code == 200
    assert captured["messages"] is not None

    system_contents = [
        m.content for m in captured["messages"] if getattr(m, "role", None) == "system"
    ]
    assert any("KB_TEST_MARKER" in c for c in system_contents)

    kb_idx = next(i for i, c in enumerate(system_contents) if "KB_TEST_MARKER" in c)
    base_idx = next(
        i
        for i, c in enumerate(system_contents)
        if "/api/v1/llm/pension-chat-stream" in c
    )
    assert kb_idx < base_idx
