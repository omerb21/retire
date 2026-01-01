import json

import app.services.llm_chat.chat_orchestration as chat_orchestration
from app.schemas.llm_chat import ChatMessage, ChatRequest
from app.services.llm_chat.chat_orchestration import run_pension_chat


def test_tax_question_does_not_trigger_transform_tool(db_session, client, monkeypatch) -> None:
    tool_call_reply = (
        '###TRANSPARENCY_LOG### {"test": true}\n'
        '###RISK_REVIEW### {"approval_required": false, "conflict_with_rag": false}\n'
        '###TOOL_CALL### {"name": "TRANSFORM_FUNDS_TO_ASSETS", "arguments": {"accounts": []}}'
    )

    def fake_chat(messages, client_id=None):
        # The orchestrator may re-prompt the LLM multiple times while blocking unsafe tools.
        # Always returning a transform TOOL_CALL lets us assert that no mutation tool is executed.
        return tool_call_reply

    monkeypatch.setattr(chat_orchestration.pension_llm_service, "chat", fake_chat)

    tool_calls: list[str] = []

    def fake_execute_tool_call(
        *,
        tool_name: str,
        args: dict,
        client_id: int,
        db,
        pension_portfolio=None,
        force_max_exemption: bool = False,
    ) -> str:
        tool_calls.append(tool_name)
        return json.dumps({"success": True}, ensure_ascii=False)

    monkeypatch.setattr(chat_orchestration, "execute_tool_call", fake_execute_tool_call)

    req = ChatRequest(
        messages=[
            ChatMessage(
                role="user", content="כמה מס אשלם אם אמשוך קצבה של 20000"
            )
        ],
        client_id=client.id,
        pension_portfolio=[],
    )

    resp = run_pension_chat(req, db_session)

    assert tool_calls == []
    assert isinstance(resp.reply, str)
