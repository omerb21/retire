import json

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def test_stream_transform_emits_pension_portfolio_update_marker(monkeypatch) -> None:
    portfolio_accounts = [
        {
            "מספר_חשבון": "A-001",
            "שם_תכנית": "קופת גמל כללית",
            "חברה_מנהלת": "חברה 1",
            "סוג_מוצר": "קופת גמל",
            "יתרה": 100000,
            "תאריך_התחלה": "2005-01-01",
            "specific_amounts": {"תגמולי_עובד_אחרי_2000": 50000},
        }
    ]

    call_count = {"n": 0}

    def fake_chat_stream(messages, client_id=None):
        call_count["n"] += 1
        if call_count["n"] == 1:
            yield (
                '###TOOL_CALL### {"name": "TRANSFORM_FUNDS_TO_ASSETS", "arguments": {"accounts": '
                + json.dumps(portfolio_accounts, ensure_ascii=False)
                + "}}"
            )
            return
        yield "PASS - done"

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
        tool_calls.append(tool_name)
        if tool_name == "TRANSFORM_FUNDS_TO_ASSETS":
            return json.dumps(
                {"success": True, "total_converted": 1, "source_data_cleared": True},
                ensure_ascii=False,
            )
        return json.dumps({"success": True}, ensure_ascii=False)

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [{"role": "user", "content": "המר"}],
            "pension_portfolio": portfolio_accounts,
        },
    )

    assert response.status_code == 200
    body = response.text
    assert "###PENSION_PORTFOLIO_UPDATE###" in body
    assert "A-001" in body
    assert tool_calls == ["TRANSFORM_FUNDS_TO_ASSETS"]
