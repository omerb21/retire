import json

import app.services.llm_chat.chat_orchestration as chat_orchestration
from app.schemas.llm_chat import ChatMessage, ChatRequest
from app.services.llm_chat.chat_orchestration import run_pension_chat


def test_non_stream_commutation_blocks_transform_tool_call(
    db_session, client, monkeypatch
) -> None:
    responses = iter(
        [
            '###TRANSPARENCY_LOG### {"test": true}\n###RISK_REVIEW### {"approval_required": false, "conflict_with_rag": false}\n###TOOL_CALL### {"name": "TRANSFORM_FUNDS_TO_ASSETS", "arguments": {"accounts": []}}',
            '###TRANSPARENCY_LOG### {"test": true}\n###RISK_REVIEW### {"approval_required": false, "conflict_with_rag": false}\n###TOOL_CALL### {"name": "EXECUTE_PENSION_COMMUTATION", "arguments": {"pension_fund_id": 1, "commutation_amount": 1000, "commutation_date": "2025-01-01", "commutation_type": "taxable", "confirmed": true}}',
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
        return json.dumps({"success": True}, ensure_ascii=False)

    monkeypatch.setattr(chat_orchestration, "execute_tool_call", fake_execute_tool_call)

    req = ChatRequest(
        messages=[ChatMessage(role="user", content="בצע היוון קצבה")],
        client_id=client.id,
        pension_portfolio=[],
    )

    resp = run_pension_chat(req, db_session)

    assert tool_calls == []
    assert isinstance(resp.reply, str)
    assert "כדי לחשב היוון" in resp.reply
    assert "מספר חשבון" in resp.reply
