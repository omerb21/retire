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
                '###TRANSPARENCY_LOG### {"test": true}\n###RISK_REVIEW### {"approval_required": false, "conflict_with_rag": false}\n###TOOL_CALL### {"name": "TRANSFORM_FUNDS_TO_ASSETS", "arguments": {"accounts": '
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

    def fake_load_latest_pension_portfolio_snapshot_models(db, client_id):
        return None

    monkeypatch.setattr(
        stream_orch,
        "load_latest_pension_portfolio_snapshot_models",
        fake_load_latest_pension_portfolio_snapshot_models,
    )

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


def test_stream_transform_portfolio_wide_after2000_is_filtered(monkeypatch) -> None:
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

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [
                {
                    "role": "user",
                    "content": "המר את כל היתרות מסוג תגמולים אחרי 2000 שיש בתיק שלי",
                }
            ],
            "pension_portfolio": portfolio_accounts,
        },
    )

    assert response.status_code == 200
    _ = response.text
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


def test_stream_transform_portfolio_wide_severance_after_settlement_is_filtered(monkeypatch) -> None:
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

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [
                {
                    "role": "user",
                    "content": "המר יתרות מסוג פיצויים לאחר התחשבנות שיש בתיק",
                }
            ],
            "pension_portfolio": portfolio_accounts,
        },
    )

    assert response.status_code == 200
    _ = response.text
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


def test_stream_transform_targeted_account_to2000_is_filtered(monkeypatch) -> None:
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

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    def fake_load_latest_pension_portfolio_snapshot_models(db, client_id):
        return None

    monkeypatch.setattr(
        stream_orch,
        "load_latest_pension_portfolio_snapshot_models",
        fake_load_latest_pension_portfolio_snapshot_models,
    )

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [
                {
                    "role": "user",
                    "content": "המר תגמולים לפני 2000 בחשבון 494930",
                }
            ],
            "pension_portfolio": portfolio_accounts,
        },
    )

    assert response.status_code == 200
    _ = response.text
    assert captured.get("tool_name") == "TRANSFORM_FUNDS_TO_ASSETS"
    args = captured.get("args") or {}
    assert args.get("use_provided_accounts_only") is True
    accounts = args.get("accounts")
    assert isinstance(accounts, list)
    assert len(accounts) == 1
    specific = accounts[0].get("specific_amounts")
    assert isinstance(specific, dict)
    assert set(specific.keys()) == {"תגמולי_עובד_עד_2000", "תגמולי_מעביד_עד_2000"}


def test_stream_transform_prev_employers_severance_katzba_is_filtered(monkeypatch) -> None:
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

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    def fake_load_latest_pension_portfolio_snapshot_models(db, client_id):
        return None

    monkeypatch.setattr(
        stream_orch,
        "load_latest_pension_portfolio_snapshot_models",
        fake_load_latest_pension_portfolio_snapshot_models,
    )

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [
                {
                    "role": "user",
                    "content": "המר את כל היתרות מסוג פיצויים מעסיקים קודמים (קצבה) שיש בתיק שלי",
                }
            ],
            "pension_portfolio": portfolio_accounts,
        },
    )

    assert response.status_code == 200
    _ = response.text
    assert captured.get("tool_name") == "TRANSFORM_FUNDS_TO_ASSETS"
    args = captured.get("args") or {}
    assert args.get("use_provided_accounts_only") is True
    accounts = args.get("accounts")
    assert isinstance(accounts, list)
    assert len(accounts) == 1
    specific = accounts[0].get("specific_amounts")
    assert isinstance(specific, dict)
    assert set(specific.keys()) == {"פיצויים_ממעסיקים_קודמים_רצף_קצבה"}


def test_stream_transform_prev_employers_severance_baatsa_merah_does_not_trigger_termination(monkeypatch) -> None:
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

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [{"role": "user", "content": "בצע המרה של פיצויים מעסיקים קודמים (קצבה)"}],
            "pension_portfolio": portfolio_accounts,
        },
    )

    assert response.status_code == 200
    _ = response.text
    assert captured.get("tool_name") == "TRANSFORM_FUNDS_TO_ASSETS"
    args = captured.get("args") or {}
    assert args.get("use_provided_accounts_only") is True
    accounts = args.get("accounts")
    assert isinstance(accounts, list)
    assert len(accounts) == 1
    specific = accounts[0].get("specific_amounts")
    assert isinstance(specific, dict)
    assert set(specific.keys()) == {"פיצויים_ממעסיקים_קודמים_רצף_קצבה"}


def test_stream_transform_after_settlement_baatsa_merah_does_not_trigger_termination(monkeypatch) -> None:
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

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [{"role": "user", "content": "בצע המרה של פיצויים לאחר התחשבנות"}],
            "pension_portfolio": portfolio_accounts,
        },
    )

    assert response.status_code == 200
    _ = response.text
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


def test_stream_transform_portfolio_wide_to2000_is_filtered(monkeypatch) -> None:
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

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [
                {
                    "role": "user",
                    "content": "המר את כל תגמולים לפני 2000 שיש במערכת",
                }
            ],
            "pension_portfolio": portfolio_accounts,
        },
    )

    assert response.status_code == 200
    _ = response.text
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


def test_stream_transform_portfolio_wide_education_fund_is_filtered(monkeypatch) -> None:
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

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [
                {
                    "role": "user",
                    "content": "בצע המרה של קרנות ההשתלמות",
                }
            ],
            "pension_portfolio": portfolio_accounts,
        },
    )

    assert response.status_code == 200
    _ = response.text
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


def test_stream_transform_portfolio_wide_to2000_baatsa_merah_is_filtered(monkeypatch) -> None:
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

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [
                {
                    "role": "user",
                    "content": "בצע המרה של תגמולים לפני 2000",
                }
            ],
            "pension_portfolio": portfolio_accounts,
        },
    )

    assert response.status_code == 200
    _ = response.text
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


def test_stream_transform_prev_employers_severance_pension_is_filtered(monkeypatch) -> None:
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

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    def fake_load_latest_pension_portfolio_snapshot_models(db, client_id):
        return None

    monkeypatch.setattr(
        stream_orch,
        "load_latest_pension_portfolio_snapshot_models",
        fake_load_latest_pension_portfolio_snapshot_models,
    )

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [
                {
                    "role": "user",
                    "content": "המר את הפיצויים ממעסיקים קודמים (קצבה)",
                }
            ],
            "pension_portfolio": portfolio_accounts,
        },
    )

    assert response.status_code == 200
    _ = response.text
    assert captured.get("tool_name") == "TRANSFORM_FUNDS_TO_ASSETS"
    args = captured.get("args") or {}
    assert args.get("use_provided_accounts_only") is True
    accounts = args.get("accounts")
    assert isinstance(accounts, list)
    assert len(accounts) == 1
    specific = accounts[0].get("specific_amounts")
    assert isinstance(specific, dict)
    assert set(specific.keys()) == {"פיצויים_ממעסיקים_קודמים_רצף_קצבה"}


def test_stream_transform_targeted_account_after2000_is_filtered(monkeypatch) -> None:
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

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    def fake_load_latest_pension_portfolio_snapshot_models(db, client_id):
        return None

    monkeypatch.setattr(
        stream_orch,
        "load_latest_pension_portfolio_snapshot_models",
        fake_load_latest_pension_portfolio_snapshot_models,
    )

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [
                {
                    "role": "user",
                    "content": "המר תגמולים אחרי 2000 בחשבון 494930",
                }
            ],
            "pension_portfolio": portfolio_accounts,
        },
    )

    assert response.status_code == 200
    _ = response.text
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
