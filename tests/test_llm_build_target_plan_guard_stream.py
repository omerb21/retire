from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def test_stream_blocks_build_target_plan_without_numeric_target(monkeypatch) -> None:
    call_count = {"n": 0}

    def fake_chat_stream(messages, client_id=None):
        call_count["n"] += 1
        if call_count["n"] == 1:
            yield '###TOOL_CALL### {"name": "BUILD_TARGET_PENSION_PLAN", "arguments": {}}'
            return
        yield "final answer"

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    def fake_execute_tool_call(*args, **kwargs) -> str:
        raise AssertionError("execute_tool_call should not be invoked for invalid BUILD_TARGET_PENSION_PLAN calls")

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [
                {
                    "role": "user",
                    "content": "אנא הצג אפשרויות משיכה מהתיק הפנסיוני והתעלם מהיתרות החסומות.",
                }
            ],
        },
    )

    assert response.status_code == 200
    assert "final answer" in response.text
    assert "Tool Output (" not in response.text
