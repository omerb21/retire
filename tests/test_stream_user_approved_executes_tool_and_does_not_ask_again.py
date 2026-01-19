import json

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def test_stream_user_approved_executes_tool_and_does_not_ask_again(monkeypatch) -> None:
    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called when user approval marker is present")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    tool_calls: list[tuple[str, dict]] = []

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
        tool_calls.append((tool_name, args))
        assert tool_name == "TRANSFORM_FUNDS_TO_ASSETS"
        assert user_approved is True
        return json.dumps({"success": True}, ensure_ascii=False)

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [
                {
                    "role": "user",
                    "content": '###USER_APPROVED### {"tool_name": "TRANSFORM_FUNDS_TO_ASSETS", "arguments": {"accounts": [], "use_provided_accounts_only": true}}',
                }
            ],
        },
    )

    assert response.status_code == 200
    assert tool_calls == [
        ("TRANSFORM_FUNDS_TO_ASSETS", {"accounts": [], "use_provided_accounts_only": True})
    ]

    body = response.text
    assert "נדרש אישור" not in body
    assert "###UI_ACTION###" not in body
    assert "🔧" in body
