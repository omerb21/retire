import json

import app.services.llm_chat.chat_orchestration as chat_orchestration
from app.schemas.llm_chat import ChatMessage, ChatRequest
from app.services.llm_chat.chat_orchestration import run_pension_chat


def test_doc_request_non_qa_blocks_non_doc_tools(
    db_session, client, monkeypatch
) -> None:
    responses = iter(
        [
            '###TRANSPARENCY_LOG### {"test": true}\n###RISK_REVIEW### {"approval_required": false, "conflict_with_rag": false}\n###TOOL_CALL### {"name": "PROCESS_TERMINATION", "arguments": {"confirmed": true}}',
            '###TRANSPARENCY_LOG### {"test": true}\n###RISK_REVIEW### {"approval_required": false, "conflict_with_rag": false}\n###TOOL_CALL### {"name": "GENERATE_FULL_REPORT", "arguments": {}}',
            "final",
        ]
    )

    def fake_chat(messages, client_id=None):
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
        if tool_name == "GENERATE_FULL_REPORT":
            return json.dumps(
                {
                    "success": True,
                    "client_id": client_id,
                    "open_path": f"/clients/{client_id}/reports?auto_html=1",
                    "status_message": "הדוח נוצר בהצלחה",
                },
                ensure_ascii=False,
            )
        return json.dumps({"success": True, "tool_name": tool_name}, ensure_ascii=False)

    monkeypatch.setattr(chat_orchestration, "execute_tool_call", fake_execute_tool_call)

    req = ChatRequest(
        messages=[
            ChatMessage(role="user", content="אנא הפק דוח מלא להורדה עבור הלקוח הנוכחי")
        ],
        client_id=client.id,
        pension_portfolio=None,
    )

    resp = run_pension_chat(req, db_session)

    assert resp.reply == "###UI_ACTION###" + resp.reply.split("###UI_ACTION###", 1)[1]
    assert "###UI_ACTION###" in resp.reply
    assert "הדוח נוצר בהצלחה" in resp.reply

    # The first tool call should be blocked; only doc tool is executed.
    assert tool_calls == ["GENERATE_FULL_REPORT"]
