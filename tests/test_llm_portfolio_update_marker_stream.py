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


def test_pension_chat_stream_does_not_500_with_additional_incomes(db_session, client, monkeypatch) -> None:
    from app.models.additional_income import AdditionalIncome
    from datetime import date
    from decimal import Decimal

    inc = AdditionalIncome(
        client_id=client.id,
        source_type="salary",
        description="salary add",
        amount=Decimal("1000"),
        frequency="monthly",
        start_date=date.today(),
        end_date=None,
        indexation_method="none",
        tax_treatment="taxable",
        tax_rate=None,
    )
    db_session.add(inc)
    db_session.commit()

    def fake_chat_stream(messages, client_id=None):
        yield "PASS - done"

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client.id,
            "messages": [{"role": "user", "content": "בדיקה"}],
            "pension_portfolio": [],
        },
    )

    assert response.status_code == 200
    assert "PASS - done" in response.text


def test_stream_full_capital_withdrawal_routes_to_max_capital_scenario(monkeypatch) -> None:
    import app.services.llm_chat.chat_stream_orchestration as stream_orch

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for deterministic max-capital routing")

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
        agent_reply: str | None = None,
        user_approved: bool = False,
    ) -> str:
        tool_calls.append(tool_name)
        if tool_name == "RUN_RETIREMENT_SCENARIOS":
            return json.dumps(
                {
                    "retirement_age": 67,
                    "scenarios": [
                        {
                            "scenario_id": 123,
                            "scenario_key": "scenario_2_max_capital",
                            "scenario_name": "מקסימום הון (קצבת מינימום: 5,500)",
                        }
                    ],
                },
                ensure_ascii=False,
            )
        return json.dumps({"success": True}, ensure_ascii=False)

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [
                {
                    "role": "user",
                    "content": "אני מעוניין למשוך את כל הסכומים בתיק בצורה הונית. בנה לי תכנית משיכה ובצע אותה",
                }
            ],
            "pension_portfolio": [
                {
                    "מספר_חשבון": "494930",
                    "שם_תכנית": "עדיף",
                    "חברה_מנהלת": "",
                    "סוג_מוצר": "פוליסת ביטוח חיים משולב חיסכון",
                    "יתרה": 100000,
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.text
    assert "EXECUTE_RETIREMENT_SCENARIO" in body
    assert "###UI_ACTION###" in body
    assert "approval_request" in body
    assert tool_calls == ["RUN_RETIREMENT_SCENARIOS"]


def test_stream_cashflow_request_runs_cashflow_tool(monkeypatch) -> None:
    import app.services.llm_chat.chat_stream_orchestration as stream_orch

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for deterministic cashflow routing")

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
        agent_reply: str | None = None,
        user_approved: bool = False,
    ) -> str:
        tool_calls.append(tool_name)
        if tool_name == "RUN_RETIREMENT_CASHFLOW_ANALYSIS":
            return json.dumps(
                {
                    "retirement_date": "2030-01-01",
                    "projected_pension": 1,
                    "monthly_tax_deduction": 1,
                    "projected_pension_net": 1,
                },
                ensure_ascii=False,
            )
        return json.dumps({"success": True}, ensure_ascii=False)

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [
                {
                    "role": "user",
                    "content": "אני זקוק להכנסה כללית של 40000 שח ברוטו בחודש. בנה לי תזרים חודשי",
                }
            ],
            "pension_portfolio": [],
        },
    )

    assert response.status_code == 200
    assert tool_calls == ["RUN_RETIREMENT_CASHFLOW_ANALYSIS"]


def test_stream_cashflow_request_parses_hebrew_thousands(monkeypatch) -> None:
    import app.services.llm_chat.chat_stream_orchestration as stream_orch

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for deterministic cashflow routing")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    captured: dict = {}

    def fake_execute_tool_call(
        *,
        tool_name: str,
        args: dict,
        client_id: int,
        db,
        pension_portfolio=None,
        force_max_exemption: bool = False,
        agent_reply: str | None = None,
        user_approved: bool = False,
    ) -> str:
        captured["tool_name"] = tool_name
        captured["args"] = args
        return json.dumps(
            {
                "retirement_date": "2030-01-01",
                "projected_pension": 1,
                "monthly_tax_deduction": 1,
                "projected_pension_net": 1,
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [
                {
                    "role": "user",
                    "content": "פרשתי לפני יומיים. אני זקוק להכנסה של 40 אלף שח ברוטו בחודש. אנא בנה לי תזרים",
                }
            ],
            "pension_portfolio": [],
        },
    )

    assert response.status_code == 200
    assert captured.get("tool_name") == "RUN_RETIREMENT_CASHFLOW_ANALYSIS"
    args = captured.get("args") or {}
    assert args.get("desired_monthly_income") == 40000.0
    assert args.get("desired_income_is_net") is False


def test_cashflow_includes_additional_income_in_gap_calculation(monkeypatch, db_session) -> None:
    from datetime import date
    from app.models.additional_income import AdditionalIncome
    from app.services.llm_agent_tools_service import AgentToolsService

    # Create taxable additional income: 12,000/month
    ai = AdditionalIncome(
        client_id=1,
        source_type="business",
        description="עסק",
        amount=12000,
        frequency="monthly",
        start_date=date(2020, 1, 1),
        end_date=None,
        indexation_method="none",
        tax_treatment="taxable",
        tax_rate=None,
        remarks=None,
    )
    db_session.add(ai)
    db_session.commit()

    agent = AgentToolsService(db_session, client_id=1, pension_portfolio_data=[])

    # Run analysis with the same desired income. We don't assert numeric values,
    # only structural expectations: additional income should be reflected.
    res = agent.run_retirement_cashflow_analysis(
        retirement_date="2026-01-02",
        desired_monthly_income=40000.0,
        apply_max_exemption=False,
        desired_income_is_net=True,
    )
    assert res.get("success") is True
    result = res.get("result") or {}
    assert result.get("additional_income_gross_monthly") == 12000.0
    assert result.get("additional_income_taxable_gross_monthly") == 12000.0
    assert (result.get("monthly_income_tax_total") or 0) >= (result.get("monthly_income_tax") or 0)
    assert (result.get("total_guaranteed_income_net") or 0) >= (result.get("projected_pension_net") or 0)


def test_stream_cashflow_ambiguous_target_prompts_gross_net(monkeypatch) -> None:
    import app.services.llm_chat.chat_stream_orchestration as stream_orch

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM should not be called for deterministic cashflow clarification")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    def fake_execute_tool_call(*args, **kwargs):
        raise AssertionError("Tool should not be called when gross/net is missing")

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [{"role": "user", "content": "פרשתי לפני יומיים. אני זקוק להכנסה של 40 אלף שח מכל המקורות ביחד. אנא בנה לי תזרים"}],
            "pension_portfolio": [],
        },
    )
    assert response.status_code == 200
    assert "ברוטו" in response.text
    assert "נטו" in response.text


def test_cashflow_tool_handler_returns_full_payload_with_explanation(monkeypatch) -> None:
    from app.services.llm_chat.tool_handlers.run_retirement_cashflow_analysis import (
        handle_run_retirement_cashflow_analysis,
    )

    class DummyAgentTools:
        def __init__(self):
            self.client = None

        def run_retirement_cashflow_analysis(self, **kwargs):
            return {
                "success": True,
                "tool_name": "RUN_RETIREMENT_CASHFLOW_ANALYSIS",
                "result": {"total_guaranteed_income_net": 1.0, "additional_income_gross_monthly": 2.0},
                "explanation": "EXPLANATION_WITH_ADDITIONAL_INCOME",
            }

    raw = handle_run_retirement_cashflow_analysis(
        args={"retirement_date": "2026-01-02", "desired_monthly_income": 40000, "desired_income_is_net": True},
        agent_tools=DummyAgentTools(),
        force_max_exemption=False,
    )

    parsed = json.loads(raw)
    assert parsed.get("success") is True
    assert parsed.get("explanation") == "EXPLANATION_WITH_ADDITIONAL_INCOME"
    assert isinstance(parsed.get("result"), dict)


def test_cashflow_formatter_prefers_explanation_when_present() -> None:
    from app.services.llm_chat.orchestration_utils import format_tool_output_for_user_stream

    payload = {
        "success": True,
        "tool_name": "RUN_RETIREMENT_CASHFLOW_ANALYSIS",
        "result": {"total_guaranteed_income_net": 1.0},
        "explanation": "EXPLAIN_ME",
    }
    out = format_tool_output_for_user_stream("RUN_RETIREMENT_CASHFLOW_ANALYSIS", json.dumps(payload))
    assert out == "EXPLAIN_ME"


def test_stream_commutation_without_account_asks_for_account(monkeypatch) -> None:
    import app.services.llm_chat.chat_stream_orchestration as stream_orch

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called when commutation is missing account")

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
        agent_reply: str | None = None,
        user_approved: bool = False,
    ) -> str:
        tool_calls.append(tool_name)
        return json.dumps({"success": True}, ensure_ascii=False)

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [
                {
                    "role": "user",
                    "content": "אני מעוניין להוון מיליון שח. כמה מס אשלם?",
                }
            ],
            "pension_portfolio": [],
        },
    )

    assert response.status_code == 200
    assert tool_calls == []
    assert "כדי לחשב היוון" in response.text
    assert "מספר חשבון" in response.text


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
