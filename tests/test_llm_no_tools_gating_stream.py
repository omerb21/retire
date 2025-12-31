from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def test_stream_qa_no_tools_blocks_tool_call(monkeypatch) -> None:
    call_count = {"n": 0}

    def fake_chat_stream(messages, client_id=None):
        call_count["n"] += 1
        if call_count["n"] == 1:
            yield '###TRANSPARENCY_LOG### {"test": true}\n###RISK_REVIEW### {"approval_required": false, "conflict_with_rag": false}\n###TOOL_CALL### {"name": "GET_PENSION_PRODUCTS", "arguments": {}}'
            return
        yield "PASS - הסבר QA ללא כלים\nסיכום קצר"

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    def fake_execute_tool_call(*args, **kwargs) -> str:
        raise AssertionError("execute_tool_call should not be invoked in no-tools mode")

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "אנא בצע בדיקת מערכת (QA) להסבר קצר בלבד. "
                        "חשוב: אין להריץ שום כלי. חובה לסיים ב-PASS/FAIL."
                    ),
                }
            ],
        },
    )

    assert response.status_code == 200
    assert "PASS" in response.text
    assert "Tool Output (" not in response.text
