import json

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def test_analysis_stop_after_tool_has_fixed_ending_without_questions(monkeypatch) -> None:
    call_count = {"n": 0}

    def fake_chat_stream(messages, client_id=None):
        call_count["n"] += 1
        if call_count["n"] == 1:
            yield '###TRANSPARENCY_LOG### {"test": true}\n###RISK_REVIEW### {"approval_required": false, "conflict_with_rag": false}\n###TOOL_CALL### {"name": "GET_PENSION_PRODUCTS", "arguments": {}}'
            return
        raise AssertionError("ANALYSIS stop-after-tool: LLM should not be called again")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    tool_calls: list[str] = []

    def fake_execute_tool_call(
        *,
        tool_name: str,
        args: dict,
        client_id: int,
        db,
        pension_portfolio=None,
        force_max_exemption: bool = False,
        agent_reply: str | None = None,
        user_approved: bool = False,
        request_id: str | None = None,
    ) -> str:
        tool_calls.append(tool_name)
        return json.dumps({"success": True}, ensure_ascii=False)

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [{"role": "user", "content": "ניתוח ותיזמון פרישה"}],
        },
    )

    assert response.status_code == 200
    assert tool_calls == ["GET_PENSION_PRODUCTS"]

    body = response.text
    assert "להסבר מילולי בלי מספרים כתוב: הסבר במילים." in body
    assert "אם תרצה" not in body
    assert "האם" not in body
    assert "?" not in body
