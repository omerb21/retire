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
            '###TRANSPARENCY_LOG### {"test": true}\n###RISK_REVIEW### {"approval_required": false, "conflict_with_rag": false}\n###TOOL_CALL### {"name": "TRANSFORM_FUNDS_TO_ASSETS", "arguments": {"accounts": '
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
        "load_latest_pension_portfolio_snapshot_models",
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
            '###TRANSPARENCY_LOG### {"test": true}\n###RISK_REVIEW### {"approval_required": false, "conflict_with_rag": false}\n###TOOL_CALL### {"name": "TRANSFORM_FUNDS_TO_ASSETS", "arguments": {"accounts": '
            + json.dumps(portfolio_accounts, ensure_ascii=False)
            + "}}",
            '###TRANSPARENCY_LOG### {"test": true}\n###RISK_REVIEW### {"approval_required": false, "conflict_with_rag": false}\n###TOOL_CALL### {"name": "GENERATE_FULL_REPORT", "arguments": {"report_type": "full"}}',
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
        "load_latest_pension_portfolio_snapshot_models",
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


def test_non_stream_transform_portfolio_wide_after2000_is_filtered(db_session, client, monkeypatch) -> None:
    portfolio_accounts = [
        {
            "מספר_חשבון": "EDU-001",
            "שם_תכנית": "מיטב השתלמות",
            "חברה_מנהלת": "חברה 1",
            "סוג_מוצר": "קרן השתלמות",
            "יתרה": 1000,
            "תאריך_התחלה": "2019-01-01",
            "specific_amounts": {
                "קרן_השתלמות": 1000,
                "תגמולי_עובד_אחרי_2008_לא_משלמת": 300,
                "תגמולי_מעביד_אחרי_2008_לא_משלמת": 700,
            },
        },
        {
            "מספר_חשבון": "PEN-001",
            "שם_תכנית": "פוליסה",
            "חברה_מנהלת": "חברה 2",
            "סוג_מוצר": "פוליסת ביטוח",
            "יתרה": 5000,
            "תאריך_התחלה": "2005-01-01",
            "specific_amounts": {
                "תגמולי_עובד_אחרי_2000": 2000,
                "תגמולי_מעביד_אחרי_2000": 3000,
                "פיצויים_לאחר_התחשבנות": 9999,
            },
        },
    ]

    responses = iter(["final"])

    def fake_chat(messages, client_id=None):
        return next(responses)

    monkeypatch.setattr(chat_orchestration.pension_llm_service, "chat", fake_chat)

    def fake_load_latest_pension_portfolio_snapshot(db, client_id):
        return None

    monkeypatch.setattr(
        chat_orchestration,
        "load_latest_pension_portfolio_snapshot_models",
        fake_load_latest_pension_portfolio_snapshot,
    )

    captured: dict = {}

    def fake_execute_tool_call(
        *,
        tool_name: str,
        args: dict,
        client_id: int,
        db,
        pension_portfolio=None,
        force_max_exemption: bool = False,
    ) -> str:
        captured["tool_name"] = tool_name
        captured["args"] = args
        return json.dumps({"success": True, "total_converted": 1}, ensure_ascii=False)

    monkeypatch.setattr(chat_orchestration, "execute_tool_call", fake_execute_tool_call)

    req = ChatRequest(
        messages=[
            ChatMessage(
                role="user",
                content="המר את כל היתרות מסוג תגמולים אחרי 2000 שיש בתיק שלי",
            )
        ],
        client_id=client.id,
        pension_portfolio=portfolio_accounts,
    )

    _ = run_pension_chat(req, db_session)

    assert captured.get("tool_name") == "TRANSFORM_FUNDS_TO_ASSETS"
    args = captured.get("args") or {}
    assert args.get("use_provided_accounts_only") is True
    accounts = args.get("accounts")
    assert isinstance(accounts, list)
    assert len(accounts) == 1
    assert str(accounts[0].get("account_number") or accounts[0].get("מספר_חשבון")) == "PEN-001"
    specific = accounts[0].get("specific_amounts")
    assert isinstance(specific, dict)
    assert set(specific.keys()) == {"תגמולי_עובד_אחרי_2000", "תגמולי_מעביד_אחרי_2000"}


def test_non_stream_transform_portfolio_wide_severance_after_settlement_is_filtered(db_session, client, monkeypatch) -> None:
    portfolio_accounts = [
        {
            "מספר_חשבון": "EDU-001",
            "שם_תכנית": "מיטב השתלמות",
            "חברה_מנהלת": "חברה 1",
            "סוג_מוצר": "קרן השתלמות",
            "יתרה": 1000,
            "תאריך_התחלה": "2019-01-01",
            "specific_amounts": {
                "קרן_השתלמות": 1000,
                "פיצויים_לאחר_התחשבנות": 9999,
            },
        },
        {
            "מספר_חשבון": "PEN-001",
            "שם_תכנית": "פוליסה",
            "חברה_מנהלת": "חברה 2",
            "סוג_מוצר": "פוליסת ביטוח",
            "יתרה": 5000,
            "תאריך_התחלה": "2005-01-01",
            "specific_amounts": {
                "תגמולי_עובד_אחרי_2000": 2000,
                "תגמולי_מעביד_אחרי_2000": 3000,
                "פיצויים_לאחר_התחשבנות": 4444,
            },
        },
    ]

    responses = iter(["final"])

    def fake_chat(messages, client_id=None):
        return next(responses)

    monkeypatch.setattr(chat_orchestration.pension_llm_service, "chat", fake_chat)

    def fake_load_latest_pension_portfolio_snapshot(db, client_id):
        return None

    monkeypatch.setattr(
        chat_orchestration,
        "load_latest_pension_portfolio_snapshot_models",
        fake_load_latest_pension_portfolio_snapshot,
    )

    captured: dict = {}

    def fake_execute_tool_call(
        *,
        tool_name: str,
        args: dict,
        client_id: int,
        db,
        pension_portfolio=None,
        force_max_exemption: bool = False,
    ) -> str:
        captured["tool_name"] = tool_name
        captured["args"] = args
        return json.dumps({"success": True, "total_converted": 1}, ensure_ascii=False)

    monkeypatch.setattr(chat_orchestration, "execute_tool_call", fake_execute_tool_call)

    req = ChatRequest(
        messages=[
            ChatMessage(
                role="user",
                content="המר יתרות מסוג פיצויים לאחר התחשבנות שיש בתיק",
            )
        ],
        client_id=client.id,
        pension_portfolio=portfolio_accounts,
    )

    _ = run_pension_chat(req, db_session)

    assert captured.get("tool_name") == "TRANSFORM_FUNDS_TO_ASSETS"
    args = captured.get("args") or {}
    assert args.get("use_provided_accounts_only") is True
    accounts = args.get("accounts")
    assert isinstance(accounts, list)
    assert len(accounts) == 1
    assert str(accounts[0].get("account_number") or accounts[0].get("מספר_חשבון")) == "PEN-001"
    specific = accounts[0].get("specific_amounts")
    assert isinstance(specific, dict)
    assert set(specific.keys()) == {"פיצויים_לאחר_התחשבנות"}


def test_non_stream_transform_targeted_account_to2000_is_filtered(db_session, client, monkeypatch) -> None:
    portfolio_accounts = [
        {
            "מספר_חשבון": "494930",
            "שם_תכנית": "עדיף",
            "חברה_מנהלת": "חברה 1",
            "סוג_מוצר": "פוליסת ביטוח",
            "יתרה": 5000,
            "תאריך_התחלה": "2005-01-01",
            "specific_amounts": {
                "תגמולי_עובד_עד_2000": 2000,
                "תגמולי_מעביד_עד_2000": 3000,
                "תגמולי_עובד_אחרי_2000": 9999,
            },
        }
    ]

    responses = iter(["final"])

    def fake_chat(messages, client_id=None):
        return next(responses)

    monkeypatch.setattr(chat_orchestration.pension_llm_service, "chat", fake_chat)

    def fake_load_latest_pension_portfolio_snapshot_models(db, client_id):
        return None

    monkeypatch.setattr(
        chat_orchestration,
        "load_latest_pension_portfolio_snapshot_models",
        fake_load_latest_pension_portfolio_snapshot_models,
    )

    captured: dict = {}

    def fake_execute_tool_call(
        *,
        tool_name: str,
        args: dict,
        client_id: int,
        db,
        pension_portfolio=None,
        force_max_exemption: bool = False,
    ) -> str:
        captured["tool_name"] = tool_name
        captured["args"] = args
        return json.dumps({"success": True, "total_converted": 1}, ensure_ascii=False)

    monkeypatch.setattr(chat_orchestration, "execute_tool_call", fake_execute_tool_call)

    req = ChatRequest(
        messages=[
            ChatMessage(
                role="user",
                content="המר תגמולים לפני 2000 בחשבון 494930",
            )
        ],
        client_id=client.id,
        pension_portfolio=portfolio_accounts,
    )

    _ = run_pension_chat(req, db_session)

    assert captured.get("tool_name") == "TRANSFORM_FUNDS_TO_ASSETS"
    args = captured.get("args") or {}
    assert args.get("use_provided_accounts_only") is True
    accounts = args.get("accounts")
    assert isinstance(accounts, list)
    assert len(accounts) == 1
    specific = accounts[0].get("specific_amounts")
    assert isinstance(specific, dict)
    assert set(specific.keys()) == {"תגמולי_עובד_עד_2000", "תגמולי_מעביד_עד_2000"}


def test_non_stream_transform_portfolio_wide_to2000_baatsa_merah_is_filtered(db_session, client, monkeypatch) -> None:
    portfolio_accounts = [
        {
            "מספר_חשבון": "EDU-001",
            "שם_תכנית": "מיטב השתלמות",
            "חברה_מנהלת": "חברה 1",
            "סוג_מוצר": "קרן השתלמות",
            "יתרה": 1000,
            "תאריך_התחלה": "2019-01-01",
            "specific_amounts": {
                "קרן_השתלמות": 1000,
                "תגמולי_עובד_עד_2000": 111,
                "תגמולי_מעביד_עד_2000": 222,
            },
        },
        {
            "מספר_חשבון": "PEN-TO-001",
            "שם_תכנית": "פוליסה",
            "חברה_מנהלת": "חברה 2",
            "סוג_מוצר": "פוליסת ביטוח",
            "יתרה": 5000,
            "תאריך_התחלה": "1999-01-01",
            "specific_amounts": {
                "תגמולי_עובד_עד_2000": 2000,
                "תגמולי_מעביד_עד_2000": 3000,
                "פיצויים_לאחר_התחשבנות": 9999,
            },
        },
    ]

    responses = iter(["final"])

    def fake_chat(messages, client_id=None):
        return next(responses)

    monkeypatch.setattr(chat_orchestration.pension_llm_service, "chat", fake_chat)

    def fake_load_latest_pension_portfolio_snapshot(db, client_id):
        return None

    monkeypatch.setattr(
        chat_orchestration,
        "load_latest_pension_portfolio_snapshot_models",
        fake_load_latest_pension_portfolio_snapshot,
    )

    captured: dict = {}

    def fake_execute_tool_call(
        *,
        tool_name: str,
        args: dict,
        client_id: int,
        db,
        pension_portfolio=None,
        force_max_exemption: bool = False,
    ) -> str:
        captured["tool_name"] = tool_name
        captured["args"] = args
        return json.dumps({"success": True, "total_converted": 1}, ensure_ascii=False)

    monkeypatch.setattr(chat_orchestration, "execute_tool_call", fake_execute_tool_call)

    req = ChatRequest(
        messages=[ChatMessage(role="user", content="בצע המרה של תגמולים לפני 2000")],
        client_id=client.id,
        pension_portfolio=portfolio_accounts,
    )

    _ = run_pension_chat(req, db_session)

    assert captured.get("tool_name") == "TRANSFORM_FUNDS_TO_ASSETS"
    args = captured.get("args") or {}
    assert args.get("use_provided_accounts_only") is True
    accounts = args.get("accounts")
    assert isinstance(accounts, list)
    assert len(accounts) == 1
    assert str(accounts[0].get("account_number") or accounts[0].get("מספר_חשבון")) == "PEN-TO-001"
    specific = accounts[0].get("specific_amounts")
    assert isinstance(specific, dict)
    assert set(specific.keys()) == {"תגמולי_עובד_עד_2000", "תגמולי_מעביד_עד_2000"}
    overrides = accounts[0].get("component_conversion_overrides")
    assert isinstance(overrides, dict)
    assert set(overrides.keys()) == {"תגמולי_עובד_עד_2000", "תגמולי_מעביד_עד_2000"}
    assert set(str(v) for v in overrides.values()) == {"capital_asset"}


def test_non_stream_transform_portfolio_wide_education_fund_is_filtered(db_session, client, monkeypatch) -> None:
    portfolio_accounts = [
        {
            "מספר_חשבון": "EDU-001",
            "שם_תכנית": "מיטב השתלמות",
            "חברה_מנהלת": "חברה 1",
            "סוג_מוצר": "קרן השתלמות",
            "יתרה": 1000,
            "תאריך_התחלה": "2019-01-01",
            "specific_amounts": {
                "קרן_השתלמות": 1000,
                "תגמולי_עובד_אחרי_2000": 111,
            },
        },
        {
            "מספר_חשבון": "PEN-001",
            "שם_תכנית": "פוליסה",
            "חברה_מנהלת": "חברה 2",
            "סוג_מוצר": "פוליסת ביטוח",
            "יתרה": 5000,
            "תאריך_התחלה": "1999-01-01",
            "specific_amounts": {
                "תגמולי_עובד_אחרי_2000": 5000,
            },
        },
    ]

    responses = iter(["final"])

    def fake_chat(messages, client_id=None):
        return next(responses)

    monkeypatch.setattr(chat_orchestration.pension_llm_service, "chat", fake_chat)

    def fake_load_latest_pension_portfolio_snapshot_models(db, client_id):
        return None

    monkeypatch.setattr(
        chat_orchestration,
        "load_latest_pension_portfolio_snapshot_models",
        fake_load_latest_pension_portfolio_snapshot_models,
    )

    captured: dict = {}

    def fake_execute_tool_call(
        *,
        tool_name: str,
        args: dict,
        client_id: int,
        db,
        pension_portfolio=None,
        force_max_exemption: bool = False,
    ) -> str:
        captured["tool_name"] = tool_name
        captured["args"] = args
        return json.dumps({"success": True, "total_converted": 1}, ensure_ascii=False)

    monkeypatch.setattr(chat_orchestration, "execute_tool_call", fake_execute_tool_call)

    req = ChatRequest(
        messages=[ChatMessage(role="user", content="בצע המרה של קרנות ההשתלמות")],
        client_id=client.id,
        pension_portfolio=portfolio_accounts,
    )

    _ = run_pension_chat(req, db_session)

    assert captured.get("tool_name") == "TRANSFORM_FUNDS_TO_ASSETS"
    args = captured.get("args") or {}
    assert args.get("use_provided_accounts_only") is True
    accounts = args.get("accounts")
    assert isinstance(accounts, list)
    assert len(accounts) == 1
    assert str(accounts[0].get("account_number") or accounts[0].get("מספר_חשבון")) == "EDU-001"
    specific = accounts[0].get("specific_amounts")
    assert isinstance(specific, dict)
    assert set(specific.keys()) == {"קרן_השתלמות"}
    overrides = accounts[0].get("component_conversion_overrides")
    assert isinstance(overrides, dict)
    assert set(overrides.keys()) == {"קרן_השתלמות"}
    assert set(str(v) for v in overrides.values()) == {"capital_asset"}


def test_non_stream_transform_prev_employers_severance_katzba_is_filtered(db_session, client, monkeypatch) -> None:
    portfolio_accounts = [
        {
            "מספר_חשבון": "494930",
            "שם_תכנית": "עדיף",
            "חברה_מנהלת": "חברה 1",
            "סוג_מוצר": "פוליסת ביטוח",
            "יתרה": 1000,
            "תאריך_התחלה": "1988-03-01",
            "specific_amounts": {
                "פיצויים_ממעסיקים_קודמים_רצף_קצבה": 123.0,
                "תגמולי_עובד_עד_2000": 10.0,
                "תגמולי_מעביד_עד_2000": 20.0,
            },
        }
    ]

    responses = iter(["final"])

    def fake_chat(messages, client_id=None):
        return next(responses)

    monkeypatch.setattr(chat_orchestration.pension_llm_service, "chat", fake_chat)

    def fake_load_latest_pension_portfolio_snapshot_models(db, client_id):
        return None

    monkeypatch.setattr(
        chat_orchestration,
        "load_latest_pension_portfolio_snapshot_models",
        fake_load_latest_pension_portfolio_snapshot_models,
    )

    captured: dict = {}

    def fake_execute_tool_call(
        *,
        tool_name: str,
        args: dict,
        client_id: int,
        db,
        pension_portfolio=None,
        force_max_exemption: bool = False,
    ) -> str:
        captured["tool_name"] = tool_name
        captured["args"] = args
        return json.dumps({"success": True, "total_converted": 1}, ensure_ascii=False)

    monkeypatch.setattr(chat_orchestration, "execute_tool_call", fake_execute_tool_call)

    req = ChatRequest(
        messages=[
            ChatMessage(
                role="user",
                content="המר את כל היתרות מסוג פיצויים מעסיקים קודמים (קצבה) שיש בתיק שלי",
            )
        ],
        client_id=client.id,
        pension_portfolio=portfolio_accounts,
    )

    _ = run_pension_chat(req, db_session)

    assert captured.get("tool_name") == "TRANSFORM_FUNDS_TO_ASSETS"
    args = captured.get("args") or {}
    assert args.get("use_provided_accounts_only") is True
    accounts = args.get("accounts")
    assert isinstance(accounts, list)
    assert len(accounts) == 1
    specific = accounts[0].get("specific_amounts")
    assert isinstance(specific, dict)
    assert set(specific.keys()) == {"פיצויים_ממעסיקים_קודמים_רצף_קצבה"}


def test_non_stream_transform_prev_employers_severance_baatsa_merah_does_not_trigger_termination(
    db_session, client, monkeypatch
) -> None:
    portfolio_accounts = [
        {
            "מספר_חשבון": "A-111",
            "שם_תכנית": "פוליסה",
            "חברה_מנהלת": "חברה 2",
            "סוג_מוצר": "פוליסת ביטוח",
            "יתרה": 5000,
            "תאריך_התחלה": "2005-01-01",
            "specific_amounts": {
                "פיצויים_ממעסיקים_קודמים_רצף_קצבה": 1234,
                "תגמולי_עובד_אחרי_2000": 9999,
            },
        }
    ]

    responses = iter(["final"])

    def fake_chat(messages, client_id=None):
        return next(responses)

    monkeypatch.setattr(chat_orchestration.pension_llm_service, "chat", fake_chat)

    def fake_load_latest_pension_portfolio_snapshot(db, client_id):
        return None

    monkeypatch.setattr(
        chat_orchestration,
        "load_latest_pension_portfolio_snapshot_models",
        fake_load_latest_pension_portfolio_snapshot,
    )

    captured: dict = {}

    def fake_execute_tool_call(
        *,
        tool_name: str,
        args: dict,
        client_id: int,
        db,
        pension_portfolio=None,
        force_max_exemption: bool = False,
    ) -> str:
        captured["tool_name"] = tool_name
        captured["args"] = args
        return json.dumps({"success": True, "total_converted": 1}, ensure_ascii=False)

    monkeypatch.setattr(chat_orchestration, "execute_tool_call", fake_execute_tool_call)

    req = ChatRequest(
        messages=[ChatMessage(role="user", content="בצע המרה של פיצויים מעסיקים קודמים (קצבה)")],
        client_id=client.id,
        pension_portfolio=portfolio_accounts,
    )

    _ = run_pension_chat(req, db_session)

    assert captured.get("tool_name") == "TRANSFORM_FUNDS_TO_ASSETS"
    args = captured.get("args") or {}
    assert args.get("use_provided_accounts_only") is True
    accounts = args.get("accounts")
    assert isinstance(accounts, list)
    assert len(accounts) == 1
    specific = accounts[0].get("specific_amounts")
    assert isinstance(specific, dict)
    assert set(specific.keys()) == {"פיצויים_ממעסיקים_קודמים_רצף_קצבה"}


def test_non_stream_transform_after_settlement_baatsa_merah_does_not_trigger_termination(
    db_session, client, monkeypatch
) -> None:
    portfolio_accounts = [
        {
            "מספר_חשבון": "PEN-001",
            "שם_תכנית": "פוליסה",
            "חברה_מנהלת": "חברה 2",
            "סוג_מוצר": "פוליסת ביטוח",
            "יתרה": 5000,
            "תאריך_התחלה": "2005-01-01",
            "specific_amounts": {
                "פיצויים_לאחר_התחשבנות": 4444,
                "תגמולי_עובד_אחרי_2000": 2000,
            },
        }
    ]

    responses = iter(["final"])

    def fake_chat(messages, client_id=None):
        return next(responses)

    monkeypatch.setattr(chat_orchestration.pension_llm_service, "chat", fake_chat)

    def fake_load_latest_pension_portfolio_snapshot(db, client_id):
        return None

    monkeypatch.setattr(
        chat_orchestration,
        "load_latest_pension_portfolio_snapshot_models",
        fake_load_latest_pension_portfolio_snapshot,
    )

    captured: dict = {}

    def fake_execute_tool_call(
        *,
        tool_name: str,
        args: dict,
        client_id: int,
        db,
        pension_portfolio=None,
        force_max_exemption: bool = False,
    ) -> str:
        captured["tool_name"] = tool_name
        captured["args"] = args
        return json.dumps({"success": True, "total_converted": 1}, ensure_ascii=False)

    monkeypatch.setattr(chat_orchestration, "execute_tool_call", fake_execute_tool_call)

    req = ChatRequest(
        messages=[ChatMessage(role="user", content="בצע המרה של פיצויים לאחר התחשבנות")],
        client_id=client.id,
        pension_portfolio=portfolio_accounts,
    )

    _ = run_pension_chat(req, db_session)

    assert captured.get("tool_name") == "TRANSFORM_FUNDS_TO_ASSETS"
    args = captured.get("args") or {}
    assert args.get("use_provided_accounts_only") is True
    accounts = args.get("accounts")
    assert isinstance(accounts, list)
    assert len(accounts) == 1
    specific = accounts[0].get("specific_amounts")
    assert isinstance(specific, dict)
    assert set(specific.keys()) == {"פיצויים_לאחר_התחשבנות"}
    overrides = accounts[0].get("component_conversion_overrides")
    assert isinstance(overrides, dict)
    assert overrides.get("פיצויים_לאחר_התחשבנות") == "capital_asset"


def test_non_stream_transform_portfolio_wide_to2000_includes_all_accounts(db_session, client, monkeypatch) -> None:
    portfolio_accounts = [
        {
            "מספר_חשבון": "494930",
            "שם_תכנית": "עדיף",
            "חברה_מנהלת": "חברה 1",
            "סוג_מוצר": "פוליסת ביטוח",
            "יתרה": 100,
            "תאריך_התחלה": "2005-01-01",
            "specific_amounts": {"תגמולי_עובד_עד_2000": 10, "תגמולי_מעביד_עד_2000": 20},
        },
        {
            "מספר_חשבון": "6120158",
            "שם_תכנית": "מיטב",
            "חברה_מנהלת": "חברה 2",
            "סוג_מוצר": "פוליסת ביטוח",
            "יתרה": 100,
            "תאריך_התחלה": "1996-01-01",
            "specific_amounts": {"תגמולי_עובד_עד_2000": 1.5, "תגמולי_מעביד_עד_2000": 2.5},
        },
    ]

    responses = iter(["final"])

    def fake_chat(messages, client_id=None):
        return next(responses)

    monkeypatch.setattr(chat_orchestration.pension_llm_service, "chat", fake_chat)

    def fake_load_latest_pension_portfolio_snapshot_models(db, client_id):
        return None

    monkeypatch.setattr(
        chat_orchestration,
        "load_latest_pension_portfolio_snapshot_models",
        fake_load_latest_pension_portfolio_snapshot_models,
    )

    captured: dict = {}

    def fake_execute_tool_call(
        *,
        tool_name: str,
        args: dict,
        client_id: int,
        db,
        pension_portfolio=None,
        force_max_exemption: bool = False,
    ) -> str:
        captured["tool_name"] = tool_name
        captured["args"] = args
        return json.dumps({"success": True, "total_converted": 1}, ensure_ascii=False)

    monkeypatch.setattr(chat_orchestration, "execute_tool_call", fake_execute_tool_call)

    req = ChatRequest(
        messages=[
            ChatMessage(
                role="user",
                content="המר את כל היתרות מסוג תגמולים לפני 2000 שיש בתיק שלי",
            )
        ],
        client_id=client.id,
        pension_portfolio=portfolio_accounts,
    )

    _ = run_pension_chat(req, db_session)

    assert captured.get("tool_name") == "TRANSFORM_FUNDS_TO_ASSETS"
    args = captured.get("args") or {}
    assert args.get("use_provided_accounts_only") is True
    accounts = args.get("accounts")
    assert isinstance(accounts, list)
    account_numbers = {str(a.get("account_number") or a.get("מספר_חשבון")) for a in accounts}
    assert account_numbers == {"494930", "6120158"}


def test_non_stream_transform_portfolio_wide_to2000_is_filtered(db_session, client, monkeypatch) -> None:
    portfolio_accounts = [
        {
            "מספר_חשבון": "EDU-001",
            "שם_תכנית": "מיטב השתלמות",
            "חברה_מנהלת": "חברה 1",
            "סוג_מוצר": "קרן השתלמות",
            "יתרה": 1000,
            "תאריך_התחלה": "2019-01-01",
            "specific_amounts": {
                "קרן_השתלמות": 1000,
                "תגמולי_עובד_עד_2000": 111,
                "תגמולי_מעביד_עד_2000": 222,
            },
        },
        {
            "מספר_חשבון": "PEN-TO-001",
            "שם_תכנית": "פוליסה",
            "חברה_מנהלת": "חברה 2",
            "סוג_מוצר": "פוליסת ביטוח",
            "יתרה": 5000,
            "תאריך_התחלה": "1999-01-01",
            "specific_amounts": {
                "תגמולי_עובד_עד_2000": 2000,
                "תגמולי_מעביד_עד_2000": 3000,
                "פיצויים_לאחר_התחשבנות": 9999,
            },
        },
    ]

    responses = iter(["final"])

    def fake_chat(messages, client_id=None):
        return next(responses)

    monkeypatch.setattr(chat_orchestration.pension_llm_service, "chat", fake_chat)

    def fake_load_latest_pension_portfolio_snapshot_models(db, client_id):
        return None

    monkeypatch.setattr(
        chat_orchestration,
        "load_latest_pension_portfolio_snapshot_models",
        fake_load_latest_pension_portfolio_snapshot_models,
    )

    captured: dict = {}

    def fake_execute_tool_call(
        *,
        tool_name: str,
        args: dict,
        client_id: int,
        db,
        pension_portfolio=None,
        force_max_exemption: bool = False,
    ) -> str:
        captured["tool_name"] = tool_name
        captured["args"] = args
        return json.dumps({"success": True, "total_converted": 1}, ensure_ascii=False)

    monkeypatch.setattr(chat_orchestration, "execute_tool_call", fake_execute_tool_call)

    req = ChatRequest(
        messages=[
            ChatMessage(
                role="user",
                content="המר את כל תגמולים לפני 2000 שיש במערכת",
            )
        ],
        client_id=client.id,
        pension_portfolio=portfolio_accounts,
    )

    _ = run_pension_chat(req, db_session)

    assert captured.get("tool_name") == "TRANSFORM_FUNDS_TO_ASSETS"
    args = captured.get("args") or {}
    assert args.get("use_provided_accounts_only") is True
    accounts = args.get("accounts")
    assert isinstance(accounts, list)
    assert len(accounts) == 1
    assert str(accounts[0].get("account_number") or accounts[0].get("מספר_חשבון")) == "PEN-TO-001"
    specific = accounts[0].get("specific_amounts")
    assert isinstance(specific, dict)
    assert set(specific.keys()) == {"תגמולי_עובד_עד_2000", "תגמולי_מעביד_עד_2000"}
    overrides = accounts[0].get("component_conversion_overrides")
    assert isinstance(overrides, dict)
    assert set(overrides.keys()) == {"תגמולי_עובד_עד_2000", "תגמולי_מעביד_עד_2000"}
    assert set(str(v) for v in overrides.values()) == {"capital_asset"}


def test_non_stream_transform_prev_employers_severance_pension_is_filtered(db_session, client, monkeypatch) -> None:
    portfolio_accounts = [
        {
            "מספר_חשבון": "A-111",
            "שם_תכנית": "כלל",
            "חברה_מנהלת": "חברה 1",
            "סוג_מוצר": "פוליסת ביטוח",
            "יתרה": 1000,
            "תאריך_התחלה": "2005-01-01",
            "specific_amounts": {
                "פיצויים_ממעסיקים_קודמים_רצף_קצבה": 777,
                "פיצויים_מעסיק_נוכחי": 999,
            },
        },
        {
            "מספר_חשבון": "B-222",
            "שם_תכנית": "אחר",
            "חברה_מנהלת": "חברה 2",
            "סוג_מוצר": "קופת גמל",
            "יתרה": 5000,
            "תאריך_התחלה": "2010-01-01",
            "specific_amounts": {
                "פיצויים_מעסיק_נוכחי": 123,
                "תגמולי_עובד_אחרי_2000": 100,
            },
        },
    ]

    responses = iter(["final"])

    def fake_chat(messages, client_id=None):
        return next(responses)

    monkeypatch.setattr(chat_orchestration.pension_llm_service, "chat", fake_chat)

    def fake_load_latest_pension_portfolio_snapshot_models(db, client_id):
        return None

    monkeypatch.setattr(
        chat_orchestration,
        "load_latest_pension_portfolio_snapshot_models",
        fake_load_latest_pension_portfolio_snapshot_models,
    )

    captured: dict = {}

    def fake_execute_tool_call(
        *,
        tool_name: str,
        args: dict,
        client_id: int,
        db,
        pension_portfolio=None,
        force_max_exemption: bool = False,
    ) -> str:
        captured["tool_name"] = tool_name
        captured["args"] = args
        return json.dumps({"success": True, "total_converted": 1}, ensure_ascii=False)

    monkeypatch.setattr(chat_orchestration, "execute_tool_call", fake_execute_tool_call)

    req = ChatRequest(
        messages=[
            ChatMessage(
                role="user",
                content="המר את הפיצויים ממעסיקים קודמים (קצבה)",
            )
        ],
        client_id=client.id,
        pension_portfolio=portfolio_accounts,
    )

    _ = run_pension_chat(req, db_session)

    assert captured.get("tool_name") == "TRANSFORM_FUNDS_TO_ASSETS"
    args = captured.get("args") or {}
    assert args.get("use_provided_accounts_only") is True
    accounts = args.get("accounts")
    assert isinstance(accounts, list)
    assert len(accounts) == 1
    specific = accounts[0].get("specific_amounts")
    assert isinstance(specific, dict)
    assert set(specific.keys()) == {"פיצויים_ממעסיקים_קודמים_רצף_קצבה"}


def test_non_stream_transform_targeted_account_after2000_is_filtered(db_session, client, monkeypatch) -> None:
    portfolio_accounts = [
        {
            "מספר_חשבון": "494930",
            "שם_תכנית": "פוליסה",
            "חברה_מנהלת": "חברה 1",
            "סוג_מוצר": "פוליסת ביטוח",
            "יתרה": 5000,
            "תאריך_התחלה": "2005-01-01",
            "specific_amounts": {
                "תגמולי_עובד_אחרי_2000": 2000,
                "תגמולי_מעביד_אחרי_2000": 3000,
                "פיצויים_לאחר_התחשבנות": 9999,
            },
        },
        {
            "מספר_חשבון": "111111",
            "שם_תכנית": "אחר",
            "חברה_מנהלת": "חברה 2",
            "סוג_מוצר": "קופת גמל",
            "יתרה": 1000,
            "תאריך_התחלה": "2010-01-01",
            "specific_amounts": {
                "תגמולי_עובד_אחרי_2000": 111,
                "תגמולי_מעביד_אחרי_2000": 222,
            },
        },
    ]

    responses = iter(["final"])

    def fake_chat(messages, client_id=None):
        return next(responses)

    monkeypatch.setattr(chat_orchestration.pension_llm_service, "chat", fake_chat)

    def fake_load_latest_pension_portfolio_snapshot_models(db, client_id):
        return None

    monkeypatch.setattr(
        chat_orchestration,
        "load_latest_pension_portfolio_snapshot_models",
        fake_load_latest_pension_portfolio_snapshot_models,
    )

    captured: dict = {}

    def fake_execute_tool_call(
        *,
        tool_name: str,
        args: dict,
        client_id: int,
        db,
        pension_portfolio=None,
        force_max_exemption: bool = False,
    ) -> str:
        captured["tool_name"] = tool_name
        captured["args"] = args
        return json.dumps({"success": True, "total_converted": 1}, ensure_ascii=False)

    monkeypatch.setattr(chat_orchestration, "execute_tool_call", fake_execute_tool_call)

    req = ChatRequest(
        messages=[
            ChatMessage(
                role="user",
                content="המר תגמולים אחרי 2000 בחשבון 494930",
            )
        ],
        client_id=client.id,
        pension_portfolio=portfolio_accounts,
    )

    _ = run_pension_chat(req, db_session)

    assert captured.get("tool_name") == "TRANSFORM_FUNDS_TO_ASSETS"
    args = captured.get("args") or {}
    assert args.get("use_provided_accounts_only") is True
    accounts = args.get("accounts")
    assert isinstance(accounts, list)
    assert len(accounts) == 1
    assert str(accounts[0].get("account_number") or accounts[0].get("מספר_חשבון")) == "494930"
    specific = accounts[0].get("specific_amounts")
    assert isinstance(specific, dict)
    assert set(specific.keys()) == {"תגמולי_עובד_אחרי_2000", "תגמולי_מעביד_אחרי_2000"}
