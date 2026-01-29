import json
from datetime import date, datetime, timezone
import inspect
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app
from app.models.additional_income import AdditionalIncome
from app.models.client import Client
from app.models.pension_fund import PensionFund
from app.models.scenario import Scenario
from app.services.llm_agent_tools_service import AgentToolsService
from app.services.additional_income_service import AdditionalIncomeService
from app.providers.tax_params import InMemoryTaxParamsProvider
from app.services.llm_chat.chat_stream_orchestration_parts import (
    stream_system_prompt_generators as stream_generators,
)
from app.services.llm_chat.chat_stream_orchestration_parts.orchestrator_impl_parts import (
    stream_loop as stream_loop_mod,
)


def test_stream_pre_retirement_plan_resolution_income_offset(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]

    client_id = 950000003

    with Session() as db:
        client = db.query(Client).filter(Client.id == client_id).first()
        if client is None:
            client = Client(
                id=client_id,
                id_number_raw=str(client_id),
                id_number=str(client_id),
                full_name="Test User",
                birth_date=date(1980, 1, 1),
                gender="male",
                is_active=True,
            )
            db.add(client)
            db.flush()

        db.add(
            AdditionalIncome(
                client_id=client_id,
                source_type="other",
                description="Test income",
                amount=Decimal("10000.00"),
                frequency="monthly",
                start_date=date(2020, 1, 1),
                end_date=None,
                indexation_method="none",
                fixed_rate=None,
                tax_treatment="fixed_rate",
                tax_rate=Decimal("10.00"),
                remarks=None,
            )
        )
        db.add(
            PensionFund(
                client_id=client_id,
                fund_name="Should not offset",
                fund_type="pension",
                input_mode="manual",
                balance=0.0,
                annuity_factor=None,
                pension_amount=99999.0,
                pension_start_date=None,
                indexation_method="none",
                fixed_index_rate=None,
                indexed_pension_amount=None,
                tax_treatment="taxable",
                remarks=None,
                deduction_file=None,
                conversion_source=None,
            )
        )
        db.commit()

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for tools-first plan request")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    with Session() as db:
        income = db.query(AdditionalIncome).filter(AdditionalIncome.client_id == client_id).first()
        income_service = AdditionalIncomeService(InMemoryTaxParamsProvider())
        today = date.today()
        reference_date = date(today.year, today.month, 1)
        monthly_gross = income_service.calculate_monthly_amount(income)
        tax_amount, _ = income_service.calculate_tax(monthly_gross, income, None, reference_date)
        expected_offset = float(monthly_gross - tax_amount)

    seen: dict[str, float] = {}

    def fake_build_target_pension_plan(
        self, target_monthly_pension, target_is_net, retirement_age=None, ignore_blocked_balances=True
    ):
        seen["target"] = float(target_monthly_pension)
        assert target_is_net is True
        return {
            "success": True,
            "tool_name": "BUILD_TARGET_PENSION_PLAN",
            "result": {
                "target_monthly_pension": float(target_monthly_pension),
                "target_is_net": bool(target_is_net),
            },
            "explanation": "OK",
        }

    monkeypatch.setattr(AgentToolsService, "build_target_pension_plan", fake_build_target_pension_plan)

    api = TestClient(app)
    resp = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "בנה תכנית יעד קצבה יעד נטו 30000"}],
            "pension_portfolio": [],
        },
    )

    assert resp.status_code == 200
    assert "###UI_ACTION###" not in resp.text
    assert "האם לכלול" not in resp.text
    assert seen.get("target") == float(30000.0 - expected_offset)


def test_stream_plan_request_not_blocked_when_undo_snapshot_exists_and_db_empty(
    monkeypatch, _test_db
) -> None:
    Session = _test_db["Session"]

    client_id = 950000007
    unique_id = f"undo-lock-{uuid4()}"

    with Session() as db:
        client = db.query(Client).filter(Client.id == client_id).first()
        if client is None:
            client = Client(
                id=client_id,
                id_number_raw=unique_id,
                id_number=unique_id,
                full_name="Test User",
                birth_date=date(1980, 1, 1),
                gender="male",
                is_active=True,
            )
            db.add(client)
            db.flush()

        snapshot_accounts = [
            {
                "מספר_חשבון": "U1",
                "שם_תכנית": "Fund U",
                "חברה_מנהלת": "X",
                "סוג_מוצר": "קופת גמל",
                "יתרה": 100000,
                "תאריך_התחלה": "2005-01-01",
                "תגמולים": 100000,
            }
        ]
        db.add(
            Scenario(
                client_id=client_id,
                scenario_name="pension_portfolio_snapshot",
                apply_tax_planning=False,
                apply_capitalization=False,
                apply_exemption_shield=False,
                parameters=json.dumps({"pension_portfolio": snapshot_accounts}, ensure_ascii=False),
                created_at=datetime.now(timezone.utc),
            )
        )

        db.query(Scenario).filter(Scenario.client_id == client_id).filter(
            Scenario.scenario_name == "undo_snapshot"
        ).delete(synchronize_session=False)
        db.add(
            Scenario(
                client_id=client_id,
                scenario_name="undo_snapshot",
                apply_tax_planning=False,
                apply_capitalization=False,
                apply_exemption_shield=False,
                parameters=json.dumps({"_meta": {"note": "undo marker"}}, ensure_ascii=False),
                created_at=datetime.now(timezone.utc),
            )
        )

        db.commit()

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for tools-first plan request")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    seen: dict[str, float] = {}

    def fake_build_target_pension_plan(
        self, target_monthly_pension, target_is_net, retirement_age=None, ignore_blocked_balances=True
    ):
        seen["target"] = float(target_monthly_pension)
        assert target_is_net is True
        return {
            "success": True,
            "tool_name": "BUILD_TARGET_PENSION_PLAN",
            "result": {
                "target_monthly_pension": float(target_monthly_pension),
                "target_is_net": bool(target_is_net),
            },
            "explanation": "OK",
        }

    monkeypatch.setattr(AgentToolsService, "build_target_pension_plan", fake_build_target_pension_plan)

    api = TestClient(app)
    resp = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "בנה תכנית יעד קצבה יעד נטו 30000"}],
            "pension_portfolio": [],
        },
    )

    assert resp.status_code == 200
    assert "כותרת: תכנית לאחר המרה" not in resp.text
    assert "לא בונים מחדש תכנית יעד" not in resp.text
    assert "כותרת: מצב תיק לאחר המרה" not in resp.text
    assert seen.get("target") == float(30000.0)


def test_stream_plan_request_not_blocked_when_snapshot_meta_indicates_transform_but_db_empty(
    monkeypatch, _test_db
) -> None:
    Session = _test_db["Session"]

    client_id = 950000006

    with Session() as db:
        client = db.query(Client).filter(Client.id == client_id).first()
        if client is None:
            client = Client(
                id=client_id,
                id_number_raw=str(client_id),
                id_number=str(client_id),
                full_name="Test User",
                birth_date=date(1980, 1, 1),
                gender="male",
                is_active=True,
            )
            db.add(client)
            db.flush()

        db.add(
            AdditionalIncome(
                client_id=client_id,
                source_type="other",
                description="Test income",
                amount=Decimal("10000.00"),
                frequency="monthly",
                start_date=date(2020, 1, 1),
                end_date=None,
                indexation_method="none",
                fixed_rate=None,
                tax_treatment="fixed_rate",
                tax_rate=Decimal("10.00"),
                remarks=None,
            )
        )

        snapshot_accounts = [
            {
                "מספר_חשבון": "A1",
                "שם_תכנית": "Fund A",
                "חברה_מנהלת": "X",
                "סוג_מוצר": "קופת גמל",
                "יתרה": 100000,
                "תאריך_התחלה": "2005-01-01",
                "תגמולים": 100000,
            }
        ]
        db.add(
            Scenario(
                client_id=client_id,
                scenario_name="pension_portfolio_snapshot",
                apply_tax_planning=False,
                apply_capitalization=False,
                apply_exemption_shield=False,
                parameters=json.dumps(
                    {
                        "pension_portfolio": snapshot_accounts,
                        "_meta": {"operation_type": "TRANSFORM_FUNDS_TO_ASSETS", "trace_id": "T-1"},
                    },
                    ensure_ascii=False,
                ),
                created_at=datetime.now(timezone.utc),
            )
        )

        db.commit()

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for tools-first plan request")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    with Session() as db:
        income = db.query(AdditionalIncome).filter(AdditionalIncome.client_id == client_id).first()
        income_service = AdditionalIncomeService(InMemoryTaxParamsProvider())
        today = date.today()
        reference_date = date(today.year, today.month, 1)
        monthly_gross = income_service.calculate_monthly_amount(income)
        tax_amount, _ = income_service.calculate_tax(monthly_gross, income, None, reference_date)
        expected_offset = float(monthly_gross - tax_amount)

    seen: dict[str, float] = {}

    def fake_build_target_pension_plan(
        self, target_monthly_pension, target_is_net, retirement_age=None, ignore_blocked_balances=True
    ):
        seen["target"] = float(target_monthly_pension)
        assert target_is_net is True
        return {
            "success": True,
            "tool_name": "BUILD_TARGET_PENSION_PLAN",
            "result": {
                "target_monthly_pension": float(target_monthly_pension),
                "target_is_net": bool(target_is_net),
            },
            "explanation": "OK",
        }

    monkeypatch.setattr(AgentToolsService, "build_target_pension_plan", fake_build_target_pension_plan)

    api = TestClient(app)
    resp = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "בנה תכנית יעד קצבה יעד נטו 30000"}],
            "pension_portfolio": [],
        },
    )

    assert resp.status_code == 200
    assert "לא בונים מחדש תכנית יעד" not in resp.text
    assert seen.get("target") == float(30000.0 - expected_offset)


def test_stream_pre_retirement_plan_resolution_blocked_question_no(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]

    client_id = 950000004

    with Session() as db:
        client = db.query(Client).filter(Client.id == client_id).first()
        if client is None:
            client = Client(
                id=client_id,
                id_number_raw=str(client_id),
                id_number=str(client_id),
                full_name="Test User",
                birth_date=date(1980, 1, 1),
                gender="male",
                is_active=True,
            )
            db.add(client)
            db.flush()

        snapshot_accounts = [
            {
                "מספר_חשבון": "B1",
                "שם_תכנית": "Fund B",
                "חברה_מנהלת": "X",
                "סוג_מוצר": "קופת גמל",
                "יתרה": 100000,
                "תאריך_התחלה": "2005-01-01",
                "פיצויים_שלא_עברו_התחשבנות": 1,
            }
        ]
        db.add(
            Scenario(
                client_id=client_id,
                scenario_name="pension_portfolio_snapshot",
                apply_tax_planning=False,
                apply_capitalization=False,
                apply_exemption_shield=False,
                parameters=json.dumps({"pension_portfolio": snapshot_accounts}, ensure_ascii=False),
                created_at=datetime.now(timezone.utc),
            )
        )
        db.commit()

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for tools-first plan request")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    def fake_build_target_pension_plan(
        self, target_monthly_pension, target_is_net, retirement_age=None, ignore_blocked_balances=True
    ):
        return {
            "success": True,
            "tool_name": "BUILD_TARGET_PENSION_PLAN",
            "result": {
                "target_monthly_pension": float(target_monthly_pension),
                "target_is_net": bool(target_is_net),
            },
            "explanation": "OK",
        }

    monkeypatch.setattr(AgentToolsService, "build_target_pension_plan", fake_build_target_pension_plan)

    original_execute_tool_call = stream_orch.execute_tool_call

    def wrapped_execute_tool_call(**kwargs):
        if kwargs.get("tool_name") == "TRANSFORM_FUNDS_TO_ASSETS":
            raise AssertionError("TRANSFORM must not run when user answered 'לא'")
        sig = inspect.signature(original_execute_tool_call)
        filtered = {k: v for k, v in kwargs.items() if k in sig.parameters}
        return original_execute_tool_call(**filtered)

    monkeypatch.setattr(stream_orch, "execute_tool_call", wrapped_execute_tool_call)

    api = TestClient(app)
    resp1 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "בנה תכנית יעד קצבה יעד נטו 5000"}],
            "pension_portfolio": [],
        },
    )
    assert resp1.status_code == 200
    assert "האם לכלול אותן בתכנון" in resp1.text
    assert "###UI_ACTION###" not in resp1.text

    resp2 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "לא"}],
            "pension_portfolio": [],
        },
    )
    assert resp2.status_code == 200
    assert "בניית תכנית קצבה" in resp2.text
    assert "###UI_ACTION###" not in resp2.text

    with Session() as db:
        pending_approval = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "pending_approval")
            .order_by(Scenario.created_at.desc())
            .first()
        )
        assert pending_approval is None


def test_stream_pre_retirement_plan_resolution_blocked_question_yes_then_approval(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]

    client_id = 950000005

    with Session() as db:
        client = db.query(Client).filter(Client.id == client_id).first()
        if client is None:
            client = Client(
                id=client_id,
                id_number_raw=str(client_id),
                id_number=str(client_id),
                full_name="Test User",
                birth_date=date(1980, 1, 1),
                gender="male",
                is_active=True,
            )
            db.add(client)
            db.flush()

        snapshot_accounts = [
            {
                "מספר_חשבון": "C1",
                "שם_תכנית": "Fund C",
                "חברה_מנהלת": "X",
                "סוג_מוצר": "קופת גמל",
                "יתרה": 100000,
                "תאריך_התחלה": "2005-01-01",
                "פיצויים_שלא_עברו_התחשבנות": 1,
            }
        ]
        db.add(
            Scenario(
                client_id=client_id,
                scenario_name="pension_portfolio_snapshot",
                apply_tax_planning=False,
                apply_capitalization=False,
                apply_exemption_shield=False,
                parameters=json.dumps({"pension_portfolio": snapshot_accounts}, ensure_ascii=False),
                created_at=datetime.now(timezone.utc),
            )
        )
        db.commit()

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for tools-first plan request")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    def fake_build_target_pension_plan(
        self, target_monthly_pension, target_is_net, retirement_age=None, ignore_blocked_balances=True
    ):
        assert float(target_monthly_pension) == 5000.0
        assert target_is_net is True
        return {
            "success": True,
            "tool_name": "BUILD_TARGET_PENSION_PLAN",
            "result": {
                "target_monthly_pension": float(target_monthly_pension),
                "target_is_net": bool(target_is_net),
            },
            "explanation": "OK",
        }

    monkeypatch.setattr(AgentToolsService, "build_target_pension_plan", fake_build_target_pension_plan)

    original_execute_tool_call = stream_orch.execute_tool_call
    tool_calls: list[str] = []

    def wrapped_execute_tool_call(
        *,
        tool_name: str,
        args: dict,
        client_id: int,
        db,
        pension_portfolio=None,
        force_max_exemption: bool = False,
        agent_reply: str | None = None,
        user_approved: bool = False,
        request_id: str | None = None,
    ) -> str:
        tool_calls.append(tool_name)
        if tool_name == "TRANSFORM_FUNDS_TO_ASSETS":
            assert user_approved is True
            assert args.get("ignore_blocked_balances") is False
            try:
                db.add(
                    PensionFund(
                        client_id=client_id,
                        fund_name="Created by transform",
                        fund_type="pension",
                        input_mode="manual",
                        balance=0.0,
                        annuity_factor=None,
                        pension_amount=10000.0,
                        pension_start_date=None,
                        indexation_method="none",
                        fixed_index_rate=None,
                        indexed_pension_amount=None,
                        tax_treatment="taxable",
                        remarks=None,
                        deduction_file=None,
                        conversion_source=None,
                    )
                )
                db.commit()
            except Exception:
                try:
                    db.rollback()
                except Exception:
                    pass
            return json.dumps(
                {
                    "success": True,
                    "tool_name": tool_name,
                    "total_converted": 1,
                    "converted_pensions": 1,
                },
                ensure_ascii=False,
            )

        sig = inspect.signature(original_execute_tool_call)
        call_kwargs = {
            "tool_name": tool_name,
            "args": args,
            "client_id": client_id,
            "db": db,
            "pension_portfolio": pension_portfolio,
            "force_max_exemption": force_max_exemption,
            "agent_reply": agent_reply,
            "user_approved": user_approved,
            "request_id": request_id,
        }
        filtered = {k: v for k, v in call_kwargs.items() if k in sig.parameters}
        return original_execute_tool_call(**filtered)

    monkeypatch.setattr(stream_orch, "execute_tool_call", wrapped_execute_tool_call)

    api = TestClient(app)

    resp1 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "בנה תכנית יעד קצבה יעד נטו 30000"}],
            "pension_portfolio": [],
        },
    )
    assert resp1.status_code == 200
    assert "האם לכלול אותן בתכנון" in resp1.text
    assert tool_calls == []

    resp2 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "כן"}],
            "pension_portfolio": [],
        },
    )
    assert resp2.status_code == 200
    assert "###UI_ACTION###" in resp2.text
    assert "TRANSFORM_FUNDS_TO_ASSETS" in resp2.text

    start = resp2.text.find("###UI_ACTION###")
    end = resp2.text.find("###END_UI_ACTION###")
    ui_payload = json.loads(resp2.text[start + len("###UI_ACTION###") : end])
    actions = ui_payload.get("actions")
    approval = actions[0]
    assert approval.get("tool_name") == "TRANSFORM_FUNDS_TO_ASSETS"
    assert approval.get("arguments", {}).get("ignore_blocked_balances") is False

    with Session() as db:
        pending = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "pending_approval")
            .order_by(Scenario.created_at.desc())
            .first()
        )
        assert pending is not None

    resp3 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "מאשר"}],
            "pension_portfolio": [],
        },
    )
    assert resp3.status_code == 200
    assert "TRANSFORM_FUNDS_TO_ASSETS" in resp3.text
    assert "בניית תכנית קצבה" in resp3.text
    assert tool_calls == ["TRANSFORM_FUNDS_TO_ASSETS", "BUILD_TARGET_PENSION_PLAN"]

    with Session() as db:
        pending_after = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "pending_approval")
            .order_by(Scenario.created_at.desc())
            .first()
        )
        assert pending_after is None


def test_stream_cashflow_uses_last_plan_without_cashflow_tool(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]

    client_id = 950000006

    with Session() as db:
        client = db.query(Client).filter(Client.id == client_id).first()
        if client is None:
            client = Client(
                id=client_id,
                id_number_raw=str(client_id),
                id_number=str(client_id),
                full_name="Test User",
                birth_date=date(1980, 1, 1),
                gender="male",
                is_active=True,
            )
            db.add(client)
            db.commit()

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    original_execute_tool_call = stream_orch.execute_tool_call
    tool_calls: list[str] = []

    def wrapped_execute_tool_call(**kwargs):
        tool_name = kwargs.get("tool_name")
        if tool_name:
            tool_calls.append(tool_name)
        assert tool_name != "RUN_RETIREMENT_CASHFLOW_ANALYSIS"
        sig = inspect.signature(original_execute_tool_call)
        filtered = {k: v for k, v in kwargs.items() if k in sig.parameters}
        return original_execute_tool_call(**filtered)

    monkeypatch.setattr(stream_orch, "execute_tool_call", wrapped_execute_tool_call)

    def fake_build_target_pension_plan(
        self, target_monthly_pension, target_is_net, retirement_age=None, ignore_blocked_balances=True
    ):
        return {
            "success": True,
            "tool_name": "BUILD_TARGET_PENSION_PLAN",
            "result": {
                "accumulated_pension": 1.0,
                "estimated_monthly_net": 1.0,
                "estimated_monthly_tax": 0.0,
                "remaining_capital": 0.0,
                "target_achieved": True,
            },
            "explanation": "OK",
        }

    monkeypatch.setattr(AgentToolsService, "build_target_pension_plan", fake_build_target_pension_plan)

    api = TestClient(app)
    resp1 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "בנה תכנית יעד קצבה יעד נטו 30000"}],
            "pension_portfolio": [],
        },
    )
    assert resp1.status_code == 200
    assert "בניית תכנית קצבה" in resp1.text

    resp2 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "תזרים"}],
            "pension_portfolio": [],
        },
    )
    assert resp2.status_code == 200
    assert "כותרת: תזרים" in resp2.text
    assert "RUN_RETIREMENT_CASHFLOW_ANALYSIS" not in resp2.text
    assert tool_calls.count("BUILD_TARGET_PENSION_PLAN") == 1
