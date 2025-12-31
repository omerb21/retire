import app.services.llm_chat.chat_orchestration as chat_orchestration
from app.schemas.llm_chat import ChatMessage, ChatRequest
from app.services.llm_chat.chat_orchestration import run_pension_chat


def test_non_stream_qa_no_tools_blocks_tool_call(db_session, client, monkeypatch) -> None:
    responses = iter(
        [
            '###TRANSPARENCY_LOG### {"test": true}\n###RISK_REVIEW### {"approval_required": false, "conflict_with_rag": false}\n###TOOL_CALL### {"name": "GET_PENSION_PRODUCTS", "arguments": {}}',
            "PASS - הסבר QA ללא כלים\nסיכום קצר",
        ]
    )

    def fake_chat(messages, client_id=None):
        return next(responses)

    monkeypatch.setattr(chat_orchestration.pension_llm_service, "chat", fake_chat)

    def fake_execute_tool_call(*args, **kwargs) -> str:
        raise AssertionError("execute_tool_call should not be invoked in no-tools mode")

    monkeypatch.setattr(chat_orchestration, "execute_tool_call", fake_execute_tool_call)

    req = ChatRequest(
        client_id=client.id,
        messages=[
            ChatMessage(
                role="user",
                content=(
                    "אנא בצע בדיקת מערכת (QA) להסבר קצר בלבד. "
                    "חשוב: אין להריץ שום כלי. חובה לסיים ב-PASS/FAIL."
                ),
            )
        ],
        pension_portfolio=None,
    )

    resp = run_pension_chat(req, db_session)
    assert "PASS" in (resp.reply or "")
    assert "###TOOL_CALL###" not in (resp.reply or "")
