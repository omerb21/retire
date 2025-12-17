import json

import pytest

import app.services.llm_chat.chat_orchestration as chat_orchestration
from app.schemas.llm_chat import ChatMessage, ChatRequest
from app.services.llm_chat.chat_orchestration import run_pension_chat


def test_qa_mode_blocks_non_qa_tools(db_session, client, monkeypatch):
    responses = iter(
        [
            '###TOOL_CALL### {"name": "PROCESS_TERMINATION", "arguments": {"confirmed": true}}',
            '###TOOL_CALL### {"name": "GET_PENSION_PRODUCTS", "arguments": {}}',
            "Final answer after QA tools",
        ]
    )

    chat_calls: list[str] = []

    def fake_chat(messages, client_id=None):
        chat_calls.append("chat")
        return next(responses)

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
        return json.dumps({"success": True, "tool_name": tool_name}, ensure_ascii=False)

    monkeypatch.setattr(chat_orchestration, "execute_tool_call", fake_execute_tool_call)

    req = ChatRequest(
        messages=[
            ChatMessage(
                role="user",
                content="אנא בצע בדיקת מערכת מקיפה (QA) ללקוח הנוכחי. הפעל GET_PENSION_PRODUCTS.",
            )
        ],
        client_id=client.id,
        pension_portfolio=None,
    )

    resp = run_pension_chat(req, db_session)

    assert resp.reply == "Final answer after QA tools"
    assert tool_calls == ["GET_PENSION_PRODUCTS"]
    assert len(chat_calls) == 3
