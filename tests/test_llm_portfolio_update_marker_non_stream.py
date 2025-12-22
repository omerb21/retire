import json

import app.services.llm_chat.chat_orchestration as chat_orchestration
from app.schemas.llm_chat import ChatMessage, ChatRequest
from app.services.llm_chat.chat_orchestration import run_pension_chat


def test_non_stream_transform_emits_pension_portfolio_update_marker(db_session, client, monkeypatch) -> None:
    portfolio_accounts = [
        {
            "מספר_חשבון": "A-001",
            "שם_תכנית": "קופת גמל כללית",
            "חברה_מנהלת": "חברה 1",
            "סוג_מוצר": "קופת גמל",
            "יתרה": 100000,
            "תאריך_התחלה": "2005-01-01",
        }
    ]

    responses = iter(
        [
            '###TOOL_CALL### {"name": "TRANSFORM_FUNDS_TO_ASSETS", "arguments": {"accounts": '
            + json.dumps(portfolio_accounts, ensure_ascii=False)
            + "}}",
            "final",
        ]
    )

    def fake_chat(messages, client_id=None):
        return next(responses)

    monkeypatch.setattr(chat_orchestration.pension_llm_service, "chat", fake_chat)

    def fake_load_latest_pension_portfolio_snapshot(db, client_id):
        return None

    monkeypatch.setattr(
        chat_orchestration,
        "load_latest_pension_portfolio_snapshot",
        fake_load_latest_pension_portfolio_snapshot,
    )

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
        return json.dumps({"success": True, "tool_name": tool_name}, ensure_ascii=False)

    monkeypatch.setattr(chat_orchestration, "execute_tool_call", fake_execute_tool_call)

    req = ChatRequest(
        messages=[ChatMessage(role="user", content="המר")],
        client_id=client.id,
        pension_portfolio=portfolio_accounts,
    )

    resp = run_pension_chat(req, db_session)

    assert "###PENSION_PORTFOLIO_UPDATE###" in resp.reply
    assert "A-001" in resp.reply
    assert tool_calls == ["TRANSFORM_FUNDS_TO_ASSETS"]


def test_non_stream_marker_is_preserved_when_document_ui_action_added(db_session, client, monkeypatch) -> None:
    portfolio_accounts = [
        {
            "מספר_חשבון": "A-001",
            "שם_תכנית": "קופת גמל כללית",
            "חברה_מנהלת": "חברה 1",
            "סוג_מוצר": "קופת גמל",
            "יתרה": 100000,
            "תאריך_התחלה": "2005-01-01",
        }
    ]

    responses = iter(
        [
            '###TOOL_CALL### {"name": "TRANSFORM_FUNDS_TO_ASSETS", "arguments": {"accounts": '
            + json.dumps(portfolio_accounts, ensure_ascii=False)
            + "}}",
            '###TOOL_CALL### {"name": "GENERATE_FULL_REPORT", "arguments": {"report_type": "full"}}',
            "final",
        ]
    )

    def fake_chat(messages, client_id=None):
        return next(responses)

    monkeypatch.setattr(chat_orchestration.pension_llm_service, "chat", fake_chat)

    def fake_load_latest_pension_portfolio_snapshot(db, client_id):
        return None

    monkeypatch.setattr(
        chat_orchestration,
        "load_latest_pension_portfolio_snapshot",
        fake_load_latest_pension_portfolio_snapshot,
    )

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
            ChatMessage(
                role="user",
                content="אנא הפק דוח מלא להורדה עבור הלקוח הנוכחי",
            )
        ],
        client_id=client.id,
        pension_portfolio=portfolio_accounts,
    )

    resp = run_pension_chat(req, db_session)

    assert "###PENSION_PORTFOLIO_UPDATE###" in resp.reply
    assert "###UI_ACTION###" in resp.reply
    assert resp.reply.index("###PENSION_PORTFOLIO_UPDATE###") < resp.reply.index("###UI_ACTION###")
    assert tool_calls == ["TRANSFORM_FUNDS_TO_ASSETS", "GENERATE_FULL_REPORT"]
