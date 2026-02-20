import json

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def test_stream_commutation_blocks_transform_tool_call(monkeypatch) -> None:
    call_count = {"n": 0}

    def fake_chat_stream(messages, client_id=None):
        call_count["n"] += 1
        if call_count["n"] == 1:
            yield (
                '###TRANSPARENCY_LOG### {"test": true}\n###RISK_REVIEW### {"approval_required": false, "conflict_with_rag": false}\n###TOOL_CALL### {"name": "TRANSFORM_FUNDS_TO_ASSETS", "arguments": {"accounts": []}}'
            )
            return

        if call_count["n"] == 2:
            yield (
                '###TRANSPARENCY_LOG### {"test": true}\n###RISK_REVIEW### {"approval_required": false, "conflict_with_rag": false}\n###TOOL_CALL### {"name": "EXECUTE_PENSION_COMMUTATION", "arguments": {"pension_fund_id": 1, "commutation_amount": 1000, "commutation_date": "2025-01-01", "commutation_type": "taxable", "confirmed": true}}'
            )
            return

        yield "final"

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
    ) -> str:
        try:
            from app.services.agent_execution.tool_execution_context import mark_tool_ok_seen

            mark_tool_ok_seen()
        except Exception:
            pass
        tool_calls.append(tool_name)
        return json.dumps({"success": True}, ensure_ascii=False)

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [{"role": "user", "content": "בצע היוון קצבה"}],
            "pension_portfolio": [],
        },
    )

    assert response.status_code == 200
    body = response.text
    assert "כדי לחשב היוון" in body
    assert "מספר חשבון" in body
    assert tool_calls == []
