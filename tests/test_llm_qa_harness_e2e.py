import json

import pytest
from datetime import date

import app.services.llm_chat.chat_orchestration as chat_orchestration
from app.services.llm_chat.chat_orchestration import run_pension_chat
from app.services.llm_chat.tool_execution import (
    execute_tool_call as real_execute_tool_call,
)
from app.schemas.llm_chat import ChatMessage, ChatRequest
from app.models.pension_fund import PensionFund
from app.models.capital_asset import CapitalAsset
from app.models.client import Client
from tests.utils import gen_valid_id


def _build_sample_portfolio() -> list[dict]:
    return [
        {
            "מספר_חשבון": "A-001",
            "שם_תכנית": "קופת גמל כללית",
            "חברה_מנהלת": "חברה 1",
            "סוג_מוצר": "קופת גמל",
            "יתרה": 100000,
            "תאריך_התחלה": "2005-01-01",
            "תגמולי_עובד_אחרי_2000": 50000,
            "תגמולי_מעביד_אחרי_2000": 50000,
        },
        {
            "מספר_חשבון": "A-002",
            "שם_תכנית": "גמל להשקעה",
            "חברה_מנהלת": "חברה 1",
            "סוג_מוצר": "קופת גמל להשקעה",
            "יתרה": 50000,
            "תאריך_התחלה": "2018-01-01",
            "תגמולי_עובד_עד_2000": 25000,
            "תגמולי_מעביד_עד_2000": 25000,
        },
        {
            "מספר_חשבון": "A-003",
            "שם_תכנית": "קרן השתלמות",
            "חברה_מנהלת": "חברה 2",
            "סוג_מוצר": "קרן השתלמות",
            "יתרה": 30000,
            "תאריך_התחלה": "2012-01-01",
            "קרן_השתלמות": 30000,
        },
        {
            "מספר_חשבון": "A-004",
            "שם_תכנית": "ביטוח מנהלים",
            "חברה_מנהלת": "חברה 3",
            "סוג_מוצר": "ביטוח מנהלים",
            "יתרה": 200000,
            "תאריך_התחלה": "1999-01-01",
            "תגמולי_עובד_אחרי_2000": 80000,
            "תגמולי_מעביד_אחרי_2000": 120000,
        },
    ]


def test_llm_qa_harness_creates_expected_assets_and_is_idempotent(
    db_session, monkeypatch
):
    portfolio = _build_sample_portfolio()

    unique_id = gen_valid_id()
    test_client = Client(
        id_number=unique_id,
        id_number_raw=unique_id,
        full_name="LLM QA Harness",
        first_name="LLM",
        last_name="Harness",
        birth_date=date(1980, 1, 1),
        gender="male",
        is_active=True,
    )
    db_session.add(test_client)
    db_session.commit()

    llm_replies = iter(
        [
            '###TRANSPARENCY_LOG### {"test": true}\n###RISK_REVIEW### {"approval_required": false, "conflict_with_rag": false}\n###TOOL_CALL### {"name": "TRANSFORM_FUNDS_TO_ASSETS", "arguments": {"accounts": '
            + json.dumps(portfolio, ensure_ascii=False)
            + "}}",
            '###TRANSPARENCY_LOG### {"test": true}\n###RISK_REVIEW### {"approval_required": false, "conflict_with_rag": false}\n###TOOL_CALL### {"name": "GET_PENSION_PRODUCTS", "arguments": {}}',
            '###TRANSPARENCY_LOG### {"test": true}\n###RISK_REVIEW### {"approval_required": false, "conflict_with_rag": false}\n###TOOL_CALL### {"name": "GENERATE_FULL_REPORT", "arguments": {"report_type": "full"}}',
            "PASS - סיכום QA סופי",
        ]
    )

    def fake_chat(messages, client_id=None):
        return next(llm_replies)

    monkeypatch.setattr(chat_orchestration.pension_llm_service, "chat", fake_chat)

    def fake_execute_tool_call(
        *,
        tool_name: str,
        args: dict,
        client_id: int,
        db,
        pension_portfolio=None,
        force_max_exemption: bool = False,
    ) -> str:
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

        return real_execute_tool_call(
            tool_name=tool_name,
            args=args,
            client_id=client_id,
            db=db,
            pension_portfolio=pension_portfolio,
            force_max_exemption=force_max_exemption,
        )

    monkeypatch.setattr(chat_orchestration, "execute_tool_call", fake_execute_tool_call)

    req = ChatRequest(
        messages=[
            ChatMessage(
                role="user",
                content="אנא בצע בדיקת מערכת מקיפה (QA) והפק דוח מלא.",
            )
        ],
        client_id=test_client.id,
        pension_portfolio=portfolio,
    )

    resp1 = run_pension_chat(req, db_session)

    assert "###UI_ACTION###" in resp1.reply
    assert "הדוח נוצר בהצלחה" in resp1.reply
    assert "PASS - סיכום QA סופי" in resp1.reply

    pension_count_1 = (
        db_session.query(PensionFund)
        .filter(PensionFund.client_id == test_client.id)
        .count()
    )
    capital_count_1 = (
        db_session.query(CapitalAsset)
        .filter(CapitalAsset.client_id == test_client.id)
        .count()
    )

    assert pension_count_1 >= 2
    assert capital_count_1 >= 2

    # Run again with same data: should not create duplicates
    llm_replies_2 = iter(
        [
            '###TRANSPARENCY_LOG### {"test": true}\n###RISK_REVIEW### {"approval_required": false, "conflict_with_rag": false}\n###TOOL_CALL### {"name": "TRANSFORM_FUNDS_TO_ASSETS", "arguments": {"accounts": '
            + json.dumps(portfolio, ensure_ascii=False)
            + "}}",
            '###TRANSPARENCY_LOG### {"test": true}\n###RISK_REVIEW### {"approval_required": false, "conflict_with_rag": false}\n###TOOL_CALL### {"name": "GET_PENSION_PRODUCTS", "arguments": {}}',
            "PASS - סיכום QA סופי",
        ]
    )

    def fake_chat_2(messages, client_id=None):
        return next(llm_replies_2)

    monkeypatch.setattr(chat_orchestration.pension_llm_service, "chat", fake_chat_2)

    resp2 = run_pension_chat(req, db_session)
    assert "PASS - סיכום QA סופי" in resp2.reply

    pension_count_2 = (
        db_session.query(PensionFund)
        .filter(PensionFund.client_id == test_client.id)
        .count()
    )
    capital_count_2 = (
        db_session.query(CapitalAsset)
        .filter(CapitalAsset.client_id == test_client.id)
        .count()
    )

    assert pension_count_2 == pension_count_1
    assert capital_count_2 == capital_count_1
