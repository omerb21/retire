import json
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app
from app.models.additional_income import AdditionalIncome
from app.models.client import Client
from app.models.current_employment.employer import CurrentEmployer
from app.models.scenario import Scenario
from app.providers.tax_params import InMemoryTaxParamsProvider
from app.services.additional_income_service import AdditionalIncomeService


def _load_pending_approval_args(Session, *, client_id: int) -> dict:
    with Session() as db:
        row = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "pending_approval")
            .order_by(Scenario.created_at.desc())
            .first()
        )
        assert row is not None
        parsed = json.loads(row.parameters)
        args = parsed.get("arguments")
        assert isinstance(args, dict)
        return dict(args)


def test_blocked_balances_notice_once_for_non_settled_and_rights(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]

    client_id = 985000001

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

        db.query(Scenario).filter(Scenario.client_id == client_id).filter(
            Scenario.scenario_name.in_(
                [
                    "pension_portfolio_snapshot",
                    "blocked_balances_notice_shown",
                    "target_pension_plan",
                    "target_pension_plan_data",
                ]
            )
        ).delete(synchronize_session=False)

        snapshot_accounts = [
            {
                "מספר_חשבון": "N1",
                "שם_תכנית": "Fund N",
                "חברה_מנהלת": "X",
                "סוג_מוצר": "קופת גמל",
                "יתרה": 100000,
                "תאריך_התחלה": "2005-01-01",
                "פיצויים_שלא_עברו_התחשבנות": 100,
                "פיצויים_ממעסיקים_קודמים_רצף_זכויות": 200,
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
        raise AssertionError("LLM must not be called for deterministic policy test")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    calls: list[tuple[str, dict]] = []

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
        request_id: str | None = None,
    ) -> str:
        calls.append((tool_name, args))
        if tool_name == "BUILD_TARGET_PENSION_PLAN":
            return json.dumps({"success": True, "result": {}}, ensure_ascii=False)
        raise AssertionError(f"Unexpected tool call: {tool_name}")

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

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
    assert "שים לב: קיימות יתרות חסומות" in resp1.text

    resp2 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "בנה תכנית יעד קצבה יעד נטו 30000"}],
            "pension_portfolio": [],
        },
    )
    assert resp2.status_code == 200
    assert "שים לב: קיימות יתרות חסומות" not in resp2.text

    with Session() as db:
        notice = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "blocked_balances_notice_shown")
            .order_by(Scenario.created_at.desc())
            .first()
        )
        assert notice is not None


def test_current_employer_severance_asks_yes_no_before_build(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]

    client_id = 985000002

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

        db.query(CurrentEmployer).filter(CurrentEmployer.client_id == client_id).delete(
            synchronize_session=False
        )
        db.add(
            CurrentEmployer(
                client_id=client_id,
                employer_name="Test Employer",
                start_date=date(2020, 1, 1),
                end_date=None,
                severance_accrued=0.0,
            )
        )

        db.query(Scenario).filter(Scenario.client_id == client_id).filter(
            Scenario.scenario_name.in_(
                [
                    "pension_portfolio_snapshot",
                    "pending_current_employer_severance_termination_question",
                ]
            )
        ).delete(synchronize_session=False)

        snapshot_accounts = [
            {
                "מספר_חשבון": "C1",
                "שם_תכנית": "Fund C",
                "חברה_מנהלת": "X",
                "סוג_מוצר": "קופת גמל",
                "יתרה": 100000,
                "תאריך_התחלה": "2005-01-01",
                "פיצויים_מעסיק_נוכחי": 1000,
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
        raise AssertionError("LLM must not be called for deterministic policy test")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    def fake_execute_tool_call(*args, **kwargs):
        raise AssertionError("Build tool must not be executed before yes/no decision")

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

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
    assert "האם תרצה לבצע עזיבת עבודה עכשיו" in resp.text

    with Session() as db:
        pending = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "pending_current_employer_severance_termination_question")
            .order_by(Scenario.created_at.desc())
            .first()
        )
        assert pending is not None


def test_current_employer_severance_nested_components_blocks_before_build(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]

    client_id = 985000005

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

        db.query(CurrentEmployer).filter(CurrentEmployer.client_id == client_id).delete(
            synchronize_session=False
        )
        db.add(
            CurrentEmployer(
                client_id=client_id,
                employer_name="Test Employer",
                start_date=date(2020, 1, 1),
                end_date=None,
                severance_accrued=0.0,
                other_grants={},
            )
        )

        db.query(Scenario).filter(Scenario.client_id == client_id).filter(
            Scenario.scenario_name.in_(
                [
                    "pension_portfolio_snapshot",
                    "pending_current_employer_severance_termination_question",
                    "current_employer_severance_execution_decision",
                    "blocked_balances_notice_shown",
                    "pending_approval",
                ]
            )
        ).delete(synchronize_session=False)

        snapshot_accounts = [
            {
                "מספר_חשבון": "C1",
                "שם_תכנית": "Fund C",
                "חברה_מנהלת": "X",
                "סוג_מוצר": "קופת גמל",
                "יתרה": 100000,
                "תאריך_התחלה": "2005-01-01",
                "components": {"פיצויים_מעסיק_נוכחי": 1000},
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
        raise AssertionError("LLM must not be called for deterministic policy test")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    def fake_execute_tool_call(*args, **kwargs):
        raise AssertionError("Build tool must not be executed when severance is blocked")

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    resp = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "בנה תכנית פרישה יעד נטו: 30000"}],
            "pension_portfolio": [],
        },
    )
    assert resp.status_code == 200
    assert "האם תרצה לבצע עזיבת עבודה עכשיו" in resp.text


def test_current_employer_severance_yes_triggers_termination_approval_and_rebuild(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]

    client_id = 985000003

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

        db.query(CurrentEmployer).filter(CurrentEmployer.client_id == client_id).delete(
            synchronize_session=False
        )
        db.add(
            CurrentEmployer(
                client_id=client_id,
                employer_name="Test Employer",
                start_date=date(2020, 1, 1),
                end_date=None,
                severance_accrued=0.0,
            )
        )

        db.query(Scenario).filter(Scenario.client_id == client_id).filter(
            Scenario.scenario_name.in_(
                [
                    "pension_portfolio_snapshot",
                    "pending_current_employer_severance_termination_question",
                    "pending_build_target_plan_after_termination",
                    "pending_approval",
                ]
            )
        ).delete(synchronize_session=False)

        snapshot_accounts = [
            {
                "מספר_חשבון": "C1",
                "שם_תכנית": "Fund C",
                "חברה_מנהלת": "X",
                "סוג_מוצר": "קופת גמל",
                "יתרה": 100000,
                "תאריך_התחלה": "2005-01-01",
                "פיצויים_מעסיק_נוכחי": 1000,
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
        raise AssertionError("LLM must not be called for deterministic policy test")

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
        request_id: str | None = None,
    ) -> str:
        tool_calls.append(tool_name)
        if tool_name == "PROCESS_TERMINATION":
            assert user_approved is True
            return json.dumps({"success": True}, ensure_ascii=False)
        if tool_name == "BUILD_TARGET_PENSION_PLAN":
            assert user_approved is True
            return json.dumps({"success": True, "result": {}}, ensure_ascii=False)
        raise AssertionError(f"Unexpected tool call: {tool_name}")

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

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
    assert "האם תרצה לבצע עזיבת עבודה עכשיו" in resp1.text

    resp2 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "כן"}],
            "pension_portfolio": [],
        },
    )
    assert resp2.status_code == 200
    assert "אני עומד לבצע עכשיו עזיבת עבודה" in resp2.text
    assert "###UI_ACTION###" not in resp2.text

    resp3 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "כן"}],
            "pension_portfolio": [],
        },
    )
    assert resp3.status_code == 200
    assert "###UI_ACTION###" in resp3.text
    assert "PROCESS_TERMINATION" in resp3.text

    pending_args = _load_pending_approval_args(Session, client_id=client_id)
    approval_payload = {"tool_name": "PROCESS_TERMINATION", "arguments": pending_args}
    resp4 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [
                {
                    "role": "user",
                    "content": f"###USER_APPROVED### {json.dumps(approval_payload, ensure_ascii=False)}",
                }
            ],
            "pension_portfolio": [],
        },
    )
    assert resp4.status_code == 200
    assert "עזיבת עבודה" in resp4.text
    assert "בניית תכנית קצבה" in resp4.text
    assert tool_calls == ["PROCESS_TERMINATION", "BUILD_TARGET_PENSION_PLAN"]


def test_current_employer_severance_yes_shows_default_plan_preview_before_approval(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]

    client_id = 985000006

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

        db.query(CurrentEmployer).filter(CurrentEmployer.client_id == client_id).delete(
            synchronize_session=False
        )
        db.add(
            CurrentEmployer(
                client_id=client_id,
                employer_name="Test Employer",
                start_date=date(2020, 1, 1),
                end_date=None,
                severance_accrued=0.0,
            )
        )

        db.query(Scenario).filter(Scenario.client_id == client_id).filter(
            Scenario.scenario_name.in_(
                [
                    "pension_portfolio_snapshot",
                    "pending_current_employer_severance_termination_question",
                    "pending_approval",
                    "current_employer_termination_plan_preview",
                ]
            )
        ).delete(synchronize_session=False)

        snapshot_accounts = [
            {
                "מספר_חשבון": "C1",
                "שם_תכנית": "Fund C",
                "חברה_מנהלת": "X",
                "סוג_מוצר": "קופת גמל",
                "יתרה": 100000,
                "תאריך_התחלה": "2005-01-01",
                "פיצויים_מעסיק_נוכחי": 1000,
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
        raise AssertionError("LLM must not be called for deterministic policy test")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    def fake_execute_tool_call(*args, **kwargs):
        raise AssertionError("No tool should run before preview confirmation")

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

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
    assert "האם תרצה לבצע עזיבת עבודה עכשיו" in resp1.text

    resp2 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "כן"}],
            "pension_portfolio": [],
        },
    )
    assert resp2.status_code == 200
    assert "אני עומד לבצע עכשיו עזיבת עבודה" in resp2.text
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


def test_current_employer_severance_preview_not_duplicated_by_build_tool_output(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]

    client_id = 985000010

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

        db.query(CurrentEmployer).filter(CurrentEmployer.client_id == client_id).delete(
            synchronize_session=False
        )
        db.add(
            CurrentEmployer(
                client_id=client_id,
                employer_name="Test Employer",
                start_date=date(2020, 1, 1),
                end_date=None,
                severance_accrued=0.0,
            )
        )

        db.query(Scenario).filter(Scenario.client_id == client_id).filter(
            Scenario.scenario_name.in_(
                [
                    "pension_portfolio_snapshot",
                    "pending_current_employer_severance_termination_question",
                    "pending_approval",
                    "current_employer_termination_plan_preview",
                ]
            )
        ).delete(synchronize_session=False)

        snapshot_accounts = [
            {
                "מספר_חשבון": "C1",
                "שם_תכנית": "Fund C",
                "חברה_מנהלת": "X",
                "סוג_מוצר": "קופת גמל",
                "יתרה": 100000,
                "תאריך_התחלה": "2005-01-01",
                "פיצויים_מעסיק_נוכחי": 1000,
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
        raise AssertionError("LLM must not be called for deterministic policy test")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    def fake_execute_tool_call(*args, **kwargs):
        raise AssertionError("BUILD must not run while waiting for preview confirmation")

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    resp1 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "בנה תכנית פרישה יעד נטו 30000"}],
            "pension_portfolio": [],
        },
    )
    assert resp1.status_code == 200
    assert "האם תרצה לבצע עזיבת עבודה עכשיו" in resp1.text

    resp2 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "כן"}],
            "pension_portfolio": [],
        },
    )
    assert resp2.status_code == 200
    assert "אני עומד לבצע עכשיו עזיבת עבודה" in resp2.text
    assert "🔧 **פלט כלי (בניית תכנית קצבה):**" not in resp2.text


def test_user_cancelled_stops_process_termination_and_clears_pending(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]

    client_id = 985000011

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

        db.query(CurrentEmployer).filter(CurrentEmployer.client_id == client_id).delete(
            synchronize_session=False
        )
        db.add(
            CurrentEmployer(
                client_id=client_id,
                employer_name="Test Employer",
                start_date=date(2020, 1, 1),
                end_date=None,
                severance_accrued=0.0,
            )
        )

        db.query(Scenario).filter(Scenario.client_id == client_id).filter(
            Scenario.scenario_name.in_(
                [
                    "pension_portfolio_snapshot",
                    "pending_current_employer_severance_termination_question",
                    "pending_approval",
                    "pending_build_target_plan_after_termination",
                    "current_employer_termination_plan_preview",
                ]
            )
        ).delete(synchronize_session=False)

        snapshot_accounts = [
            {
                "מספר_חשבון": "C1",
                "שם_תכנית": "Fund C",
                "חברה_מנהלת": "X",
                "סוג_מוצר": "קופת גמל",
                "יתרה": 100000,
                "תאריך_התחלה": "2005-01-01",
                "פיצויים_מעסיק_נוכחי": 1000,
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
        raise AssertionError("LLM must not be called for deterministic policy test")

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
        request_id: str | None = None,
    ) -> str:
        tool_calls.append(tool_name)
        raise AssertionError("No tool should execute after USER_CANCELLED")

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

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
    assert "האם תרצה לבצע עזיבת עבודה עכשיו" in resp1.text

    resp2 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "כן"}],
            "pension_portfolio": [],
        },
    )
    assert resp2.status_code == 200
    assert "אני עומד לבצע עכשיו עזיבת עבודה" in resp2.text

    resp3 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "כן"}],
            "pension_portfolio": [],
        },
    )
    assert resp3.status_code == 200
    assert "###UI_ACTION###" in resp3.text
    assert "PROCESS_TERMINATION" in resp3.text

    cancelled_payload = {"tool_name": "PROCESS_TERMINATION", "arguments": {"confirmed": True}}
    resp4 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [
                {
                    "role": "user",
                    "content": f"###USER_CANCELLED### {json.dumps(cancelled_payload, ensure_ascii=False)}",
                }
            ],
            "pension_portfolio": [],
        },
    )
    assert resp4.status_code == 200
    assert "בוצעה ביטול להפעלת הכלי" in resp4.text
    assert tool_calls == []

    with Session() as db:
        pending = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "pending_approval")
            .order_by(Scenario.created_at.desc())
            .first()
        )
        assert pending is None

        pending_build = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "pending_build_target_plan_after_termination")
            .order_by(Scenario.created_at.desc())
            .first()
        )
        assert pending_build is None


def test_user_approved_process_termination_cannot_bypass_preview(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]

    client_id = 985000012

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

        db.query(CurrentEmployer).filter(CurrentEmployer.client_id == client_id).delete(
            synchronize_session=False
        )
        db.add(
            CurrentEmployer(
                client_id=client_id,
                employer_name="Test Employer",
                start_date=date(2020, 1, 1),
                end_date=None,
                severance_accrued=0.0,
            )
        )

        db.query(Scenario).filter(Scenario.client_id == client_id).filter(
            Scenario.scenario_name.in_(
                [
                    "pension_portfolio_snapshot",
                    "pending_current_employer_severance_termination_question",
                    "pending_approval",
                    "pending_build_target_plan_after_termination",
                    "current_employer_termination_plan_preview",
                ]
            )
        ).delete(synchronize_session=False)

        snapshot_accounts = [
            {
                "מספר_חשבון": "C1",
                "שם_תכנית": "Fund C",
                "חברה_מנהלת": "X",
                "סוג_מוצר": "קופת גמל",
                "יתרה": 100000,
                "תאריך_התחלה": "2005-01-01",
                "פיצויים_מעסיק_נוכחי": 1000,
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
        raise AssertionError("LLM must not be called for deterministic policy test")

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
        request_id: str | None = None,
    ) -> str:
        tool_calls.append(tool_name)
        raise AssertionError("PROCESS_TERMINATION must not execute before preview approval")

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)

    resp1 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "בנה תכנית פרישה יעד נטו 30000"}],
            "pension_portfolio": [],
        },
    )
    assert resp1.status_code == 200
    assert "האם תרצה לבצע עזיבת עבודה עכשיו" in resp1.text

    approved_payload = {
        "tool_name": "PROCESS_TERMINATION",
        "arguments": {"confirmed": True, "exempt_choice": "redeem_with_exemption", "taxable_choice": "annuity"},
    }
    resp2 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [
                {
                    "role": "user",
                    "content": f"###USER_APPROVED### {json.dumps(approved_payload, ensure_ascii=False)}",
                }
            ],
            "pension_portfolio": [],
        },
    )
    assert resp2.status_code == 200
    assert "אני עומד לבצע עכשיו עזיבת עבודה בברירת המחדל" in resp2.text
    assert "###UI_ACTION###" not in resp2.text
    assert "בוצע בהצלחה" not in resp2.text
    assert tool_calls == []

    resp3 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "כן"}],
            "pension_portfolio": [],
        },
    )
    assert resp3.status_code == 200
    assert "###UI_ACTION###" in resp3.text
    assert "PROCESS_TERMINATION" in resp3.text


def test_current_employer_termination_preview_decline_stops_and_asks_alternatives(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]

    client_id = 985000007

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

        db.query(CurrentEmployer).filter(CurrentEmployer.client_id == client_id).delete(
            synchronize_session=False
        )
        db.add(
            CurrentEmployer(
                client_id=client_id,
                employer_name="Test Employer",
                start_date=date(2020, 1, 1),
                end_date=None,
                severance_accrued=0.0,
            )
        )

        db.query(Scenario).filter(Scenario.client_id == client_id).filter(
            Scenario.scenario_name.in_(
                [
                    "pension_portfolio_snapshot",
                    "pending_current_employer_severance_termination_question",
                    "pending_approval",
                    "pending_build_target_plan_after_termination",
                    "current_employer_termination_plan_preview",
                ]
            )
        ).delete(synchronize_session=False)

        snapshot_accounts = [
            {
                "מספר_חשבון": "C1",
                "שם_תכנית": "Fund C",
                "חברה_מנהלת": "X",
                "סוג_מוצר": "קופת גמל",
                "יתרה": 100000,
                "תאריך_התחלה": "2005-01-01",
                "פיצויים_מעסיק_נוכחי": 1000,
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
        raise AssertionError("LLM must not be called for deterministic policy test")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    def fake_execute_tool_call(*args, **kwargs):
        raise AssertionError("No tool should run when preview is declined")

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

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
    assert "האם תרצה לבצע עזיבת עבודה עכשיו" in resp1.text

    resp2 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "כן"}],
            "pension_portfolio": [],
        },
    )
    assert resp2.status_code == 200
    assert "אני עומד לבצע עכשיו עזיבת עבודה" in resp2.text

    resp3 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "לא"}],
            "pension_portfolio": [],
        },
    )
    assert resp3.status_code == 200
    assert "כדי להמשיך, כתוב מה אתה רוצה לעשות עם הפיצויים" in resp3.text
    assert "###UI_ACTION###" not in resp3.text

    with Session() as db:
        pending_approval = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "pending_approval")
            .order_by(Scenario.created_at.desc())
            .first()
        )
        assert pending_approval is None
        pending_build = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "pending_build_target_plan_after_termination")
            .order_by(Scenario.created_at.desc())
            .first()
        )
        assert pending_build is None


def test_current_employer_termination_approved_rebuild_uses_refreshed_snapshot_and_offsets(
    monkeypatch, _test_db
) -> None:
    Session = _test_db["Session"]

    client_id = 985000008

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

        db.query(CurrentEmployer).filter(CurrentEmployer.client_id == client_id).delete(
            synchronize_session=False
        )
        db.add(
            CurrentEmployer(
                client_id=client_id,
                employer_name="Test Employer",
                start_date=date(2020, 1, 1),
                end_date=None,
                severance_accrued=0.0,
            )
        )

        db.query(Scenario).filter(Scenario.client_id == client_id).filter(
            Scenario.scenario_name.in_(
                [
                    "pension_portfolio_snapshot",
                    "pending_current_employer_severance_termination_question",
                    "pending_build_target_plan_after_termination",
                    "pending_approval",
                    "current_employer_termination_plan_preview",
                    "current_employer_severance_execution_decision",
                ]
            )
        ).delete(synchronize_session=False)
        db.commit()

    with Session() as db:
        income = (
            db.query(AdditionalIncome)
            .filter(AdditionalIncome.client_id == client_id)
            .order_by(AdditionalIncome.id.desc())
            .first()
        )
        income_service = AdditionalIncomeService(InMemoryTaxParamsProvider())
        today = date.today()
        reference_date = date(today.year, today.month, 1)
        monthly_gross = income_service.calculate_monthly_amount(income)
        tax_amount, _ = income_service.calculate_tax(monthly_gross, income, None, reference_date)
        expected_offset = float(monthly_gross - tax_amount)

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for deterministic policy test")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    portfolio_before = [
        {
            "מספר_חשבון": "C1",
            "שם_תכנית": "Fund C",
            "חברה_מנהלת": "X",
            "סוג_מוצר": "קופת גמל",
            "יתרה": 100000,
            "תאריך_התחלה": "2005-01-01",
            "פיצויים_מעסיק_נוכחי": 1000,
        }
    ]
    portfolio_after = [
        {
            "מספר_חשבון": "C1",
            "שם_תכנית": "Fund C",
            "חברה_מנהלת": "X",
            "סוג_מוצר": "קופת גמל",
            "יתרה": 100000,
            "תאריך_התחלה": "2005-01-01",
            "תגמולים": 100000,
        }
    ]

    load_calls = {"n": 0}

    def fake_loader(db, client_id_in):
        load_calls["n"] += 1
        if load_calls["n"] >= 2:
            return portfolio_after, datetime.now(timezone.utc)
        return portfolio_before, datetime.now(timezone.utc)

    monkeypatch.setattr(stream_orch, "load_latest_pension_portfolio_snapshot_models", fake_loader)

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
        request_id: str | None = None,
    ) -> str:
        tool_calls.append(tool_name)
        if tool_name == "PROCESS_TERMINATION":
            return json.dumps({"success": True}, ensure_ascii=False)
        if tool_name == "BUILD_TARGET_PENSION_PLAN":
            assert pension_portfolio == portfolio_after
            assert args.get("target_monthly_pension") == float(30000.0 - expected_offset)
            return json.dumps({"success": True, "result": {}}, ensure_ascii=False)
        raise AssertionError(f"Unexpected tool call: {tool_name}")

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

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
    assert "האם תרצה לבצע עזיבת עבודה עכשיו" in resp1.text

    resp2 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "כן"}],
            "pension_portfolio": [],
        },
    )
    assert resp2.status_code == 200
    assert "אני עומד לבצע עכשיו עזיבת עבודה" in resp2.text

    resp3 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "כן"}],
            "pension_portfolio": [],
        },
    )
    assert resp3.status_code == 200
    assert "###UI_ACTION###" in resp3.text
    assert "PROCESS_TERMINATION" in resp3.text

    pending_args = _load_pending_approval_args(Session, client_id=client_id)
    approval_payload = {"tool_name": "PROCESS_TERMINATION", "arguments": pending_args}
    resp4 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [
                {
                    "role": "user",
                    "content": f"###USER_APPROVED### {json.dumps(approval_payload, ensure_ascii=False)}",
                }
            ],
            "pension_portfolio": [],
        },
    )
    assert resp4.status_code == 200
    assert tool_calls == ["PROCESS_TERMINATION", "BUILD_TARGET_PENSION_PLAN"]


def test_current_employer_termination_failure_does_not_rebuild_plan(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]

    client_id = 985000009

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

        db.query(CurrentEmployer).filter(CurrentEmployer.client_id == client_id).delete(
            synchronize_session=False
        )
        db.add(
            CurrentEmployer(
                client_id=client_id,
                employer_name="Test Employer",
                start_date=date(2020, 1, 1),
                end_date=None,
                severance_accrued=0.0,
            )
        )

        db.query(Scenario).filter(Scenario.client_id == client_id).filter(
            Scenario.scenario_name.in_(
                [
                    "pension_portfolio_snapshot",
                    "pending_current_employer_severance_termination_question",
                    "pending_build_target_plan_after_termination",
                    "pending_approval",
                    "current_employer_termination_plan_preview",
                ]
            )
        ).delete(synchronize_session=False)

        snapshot_accounts = [
            {
                "מספר_חשבון": "C1",
                "שם_תכנית": "Fund C",
                "חברה_מנהלת": "X",
                "סוג_מוצר": "קופת גמל",
                "יתרה": 100000,
                "תאריך_התחלה": "2005-01-01",
                "פיצויים_מעסיק_נוכחי": 1000,
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
        raise AssertionError("LLM must not be called for deterministic policy test")

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
        request_id: str | None = None,
    ) -> str:
        tool_calls.append(tool_name)
        if tool_name == "PROCESS_TERMINATION":
            return json.dumps({"success": False, "error": "FAILED"}, ensure_ascii=False)
        if tool_name == "BUILD_TARGET_PENSION_PLAN":
            raise AssertionError("Build must not be executed when termination fails")
        raise AssertionError(f"Unexpected tool call: {tool_name}")

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

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
    assert "האם תרצה לבצע עזיבת עבודה עכשיו" in resp1.text

    resp2 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "כן"}],
            "pension_portfolio": [],
        },
    )
    assert resp2.status_code == 200
    assert "אני עומד לבצע עכשיו עזיבת עבודה" in resp2.text

    resp3 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "כן"}],
            "pension_portfolio": [],
        },
    )
    assert resp3.status_code == 200
    assert "###UI_ACTION###" in resp3.text

    pending_args = _load_pending_approval_args(Session, client_id=client_id)
    approval_payload = {"tool_name": "PROCESS_TERMINATION", "arguments": pending_args}
    resp4 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [
                {
                    "role": "user",
                    "content": f"###USER_APPROVED### {json.dumps(approval_payload, ensure_ascii=False)}",
                }
            ],
            "pension_portfolio": [],
        },
    )
    assert resp4.status_code == 200
    assert tool_calls == ["PROCESS_TERMINATION"]


def test_current_employer_severance_no_builds_ignoring(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]

    client_id = 985000004

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

        db.query(CurrentEmployer).filter(CurrentEmployer.client_id == client_id).delete(
            synchronize_session=False
        )
        db.add(
            CurrentEmployer(
                client_id=client_id,
                employer_name="Test Employer",
                start_date=date(2020, 1, 1),
                end_date=None,
                severance_accrued=0.0,
            )
        )

        db.query(Scenario).filter(Scenario.client_id == client_id).filter(
            Scenario.scenario_name.in_(
                [
                    "pension_portfolio_snapshot",
                    "pending_current_employer_severance_termination_question",
                    "current_employer_severance_execution_decision",
                ]
            )
        ).delete(synchronize_session=False)

        snapshot_accounts = [
            {
                "מספר_חשבון": "C1",
                "שם_תכנית": "Fund C",
                "חברה_מנהלת": "X",
                "סוג_מוצר": "קופת גמל",
                "יתרה": 100000,
                "תאריך_התחלה": "2005-01-01",
                "פיצויים_מעסיק_נוכחי": 1000,
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
        raise AssertionError("LLM must not be called for deterministic policy test")

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
        request_id: str | None = None,
    ) -> str:
        tool_calls.append(tool_name)
        assert tool_name == "BUILD_TARGET_PENSION_PLAN"
        assert args.get("ignore_blocked_balances") is True
        return json.dumps({"success": True, "result": {}}, ensure_ascii=False)

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

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
    assert "האם תרצה לבצע עזיבת עבודה עכשיו" in resp1.text

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
    assert tool_calls == ["BUILD_TARGET_PENSION_PLAN"]


def test_termination_declined_then_all_to_annuity_shows_preview_and_gates_execution(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]
    client_id = 985000020

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

        db.query(CurrentEmployer).filter(CurrentEmployer.client_id == client_id).delete(
            synchronize_session=False
        )
        db.add(
            CurrentEmployer(
                client_id=client_id,
                employer_name="Test Employer",
                start_date=date(2020, 1, 1),
                end_date=None,
                severance_accrued=0.0,
            )
        )

        db.query(Scenario).filter(Scenario.client_id == client_id).filter(
            Scenario.scenario_name.in_(
                [
                    "pension_portfolio_snapshot",
                    "pending_current_employer_severance_termination_question",
                    "pending_build_target_plan_after_termination",
                    "pending_approval",
                    "current_employer_termination_plan_preview",
                    "current_employer_severance_execution_decision",
                ]
            )
        ).delete(synchronize_session=False)

        snapshot_accounts = [
            {
                "מספר_חשבון": "C1",
                "שם_תכנית": "Fund C",
                "חברה_מנהלת": "X",
                "סוג_מוצר": "קופת גמל",
                "יתרה": 100000,
                "תאריך_התחלה": "2005-01-01",
                "פיצויים_מעסיק_נוכחי": 1000,
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
        raise AssertionError("LLM must not be called for deterministic policy test")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    tool_calls: list[str] = []

    def fake_execute_tool_call(
        tool_name: str,
        args: dict,
        client_id: int,
        db,
        pension_portfolio=None,
        force_max_exemption: bool = False,
        agent_reply: str | None = None,
        user_approved: bool = False,
        request_id: str | None = None,
        **kwargs,
    ) -> str:
        assert isinstance(tool_name, str)
        assert isinstance(args, dict)
        tool_calls.append(tool_name)
        if tool_name == "PROCESS_TERMINATION":
            assert user_approved is True
            assert args.get("exempt_choice") == "annuity"
            assert args.get("taxable_choice") == "annuity"
            return json.dumps({"success": True}, ensure_ascii=False)
        if tool_name == "BUILD_TARGET_PENSION_PLAN":
            assert user_approved is True
            return json.dumps({"success": True, "result": {}}, ensure_ascii=False)
        raise AssertionError(f"Unexpected tool call: {tool_name}")

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

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
    assert "האם תרצה לבצע עזיבת עבודה עכשיו" in resp1.text

    resp2 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "כן"}],
            "pension_portfolio": [],
        },
    )
    assert resp2.status_code == 200
    assert "אני עומד לבצע עכשיו עזיבת עבודה" in resp2.text

    resp3 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "לא"}],
            "pension_portfolio": [],
        },
    )
    assert resp3.status_code == 200
    assert "כדי להמשיך, כתוב מה אתה רוצה לעשות עם הפיצויים" in resp3.text
    assert tool_calls == []

    resp4 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "למשוך את הכל כקצבה"}],
            "pension_portfolio": [],
        },
    )
    assert resp4.status_code == 200
    assert "לפי הבחירה שביקשת" in resp4.text
    assert "לאשר את התכנית הזו" in resp4.text
    assert "###UI_ACTION###" not in resp4.text
    assert tool_calls == []

    resp5 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "כן"}],
            "pension_portfolio": [],
        },
    )
    assert resp5.status_code == 200
    assert "###UI_ACTION###" in resp5.text
    assert "PROCESS_TERMINATION" in resp5.text

    pending_args = _load_pending_approval_args(Session, client_id=client_id)
    approval_payload = {"tool_name": "PROCESS_TERMINATION", "arguments": pending_args}
    resp6 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [
                {
                    "role": "user",
                    "content": f"###USER_APPROVED### {json.dumps(approval_payload, ensure_ascii=False)}",
                }
            ],
            "pension_portfolio": [],
        },
    )
    assert resp6.status_code == 200
    assert tool_calls == ["PROCESS_TERMINATION", "BUILD_TARGET_PENSION_PLAN"]


def test_termination_declined_then_exempt_and_taxable_annuity_parses(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]
    client_id = 985000021

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

        db.query(CurrentEmployer).filter(CurrentEmployer.client_id == client_id).delete(
            synchronize_session=False
        )
        db.add(
            CurrentEmployer(
                client_id=client_id,
                employer_name="Test Employer",
                start_date=date(2020, 1, 1),
                end_date=None,
                severance_accrued=0.0,
            )
        )

        db.query(Scenario).filter(Scenario.client_id == client_id).filter(
            Scenario.scenario_name.in_(
                [
                    "pension_portfolio_snapshot",
                    "pending_current_employer_severance_termination_question",
                    "pending_build_target_plan_after_termination",
                    "pending_approval",
                    "current_employer_termination_plan_preview",
                    "current_employer_severance_execution_decision",
                ]
            )
        ).delete(synchronize_session=False)

        snapshot_accounts = [
            {
                "מספר_חשבון": "C1",
                "שם_תכנית": "Fund C",
                "חברה_מנהלת": "X",
                "סוג_מוצר": "קופת גמל",
                "יתרה": 100000,
                "תאריך_התחלה": "2005-01-01",
                "פיצויים_מעסיק_נוכחי": 1000,
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
        raise AssertionError("LLM must not be called for deterministic policy test")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    tool_calls: list[str] = []

    def fake_execute_tool_call(*args, **kwargs) -> str:
        tool_name = kwargs.get("tool_name")
        tool_args = kwargs.get("args")
        user_approved = kwargs.get("user_approved")
        if tool_name is None and args:
            tool_name = args[0] if len(args) > 0 else None
            tool_args = args[1] if len(args) > 1 else None
            if user_approved is None and len(args) > 7:
                user_approved = args[7]

        assert isinstance(tool_name, str)
        assert isinstance(tool_args, dict)
        tool_calls.append(tool_name)
        if tool_name == "PROCESS_TERMINATION":
            assert user_approved is True
            assert tool_args.get("exempt_choice") == "annuity"
            assert tool_args.get("taxable_choice") == "annuity"
            return json.dumps({"success": True}, ensure_ascii=False)
        if tool_name == "BUILD_TARGET_PENSION_PLAN":
            assert user_approved is True
            return json.dumps({"success": True, "result": {}}, ensure_ascii=False)
        raise AssertionError(f"Unexpected tool call: {tool_name}")

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

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

    resp2 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "כן"}],
            "pension_portfolio": [],
        },
    )
    assert resp2.status_code == 200
    assert "אני עומד לבצע עכשיו עזיבת עבודה" in resp2.text

    resp3 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "לא"}],
            "pension_portfolio": [],
        },
    )
    assert resp3.status_code == 200
    assert "כדי להמשיך, כתוב מה אתה רוצה לעשות עם הפיצויים" in resp3.text

    resp4 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "פטור לקצבה, חייב לקצבה"}],
            "pension_portfolio": [],
        },
    )
    assert resp4.status_code == 200
    assert "לפי הבחירה שביקשת" in resp4.text
    assert tool_calls == []


def test_termination_alternative_unparseable_keeps_state_and_asks_clarifying_question(
    monkeypatch, _test_db
) -> None:
    Session = _test_db["Session"]
    client_id = 985000022

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

        db.query(CurrentEmployer).filter(CurrentEmployer.client_id == client_id).delete(
            synchronize_session=False
        )
        db.add(
            CurrentEmployer(
                client_id=client_id,
                employer_name="Test Employer",
                start_date=date(2020, 1, 1),
                end_date=None,
                severance_accrued=0.0,
            )
        )

        db.query(Scenario).filter(Scenario.client_id == client_id).filter(
            Scenario.scenario_name.in_(
                [
                    "pension_portfolio_snapshot",
                    "pending_current_employer_severance_termination_question",
                    "pending_build_target_plan_after_termination",
                    "pending_approval",
                    "current_employer_termination_plan_preview",
                    "current_employer_severance_execution_decision",
                ]
            )
        ).delete(synchronize_session=False)

        snapshot_accounts = [
            {
                "מספר_חשבון": "C1",
                "שם_תכנית": "Fund C",
                "חברה_מנהלת": "X",
                "סוג_מוצר": "קופת גמל",
                "יתרה": 100000,
                "תאריך_התחלה": "2005-01-01",
                "פיצויים_מעסיק_נוכחי": 1000,
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
        raise AssertionError("LLM must not be called when awaiting termination alternative")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    def fake_execute_tool_call(*args, **kwargs):
        raise AssertionError("No tools must be executed for unparseable alternative")

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

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

    resp2 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "כן"}],
            "pension_portfolio": [],
        },
    )
    assert resp2.status_code == 200
    assert "אני עומד לבצע עכשיו עזיבת עבודה" in resp2.text

    resp3 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "לא"}],
            "pension_portfolio": [],
        },
    )
    assert resp3.status_code == 200
    assert "כדי להמשיך, כתוב מה אתה רוצה לעשות עם הפיצויים" in resp3.text

    resp4 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "תעשה מה שאתה חושב"}],
            "pension_portfolio": [],
        },
    )
    assert resp4.status_code == 200
    assert "לא הבנתי בדיוק" in resp4.text
    assert "אני יכול להסביר את העיקרון בלבד" not in resp4.text

    with Session() as db:
        pending = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "pending_current_employer_severance_termination_question")
            .order_by(Scenario.created_at.desc())
            .first()
        )
        assert pending is None

        decision = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "current_employer_severance_execution_decision")
            .order_by(Scenario.created_at.desc())
            .first()
        )
        assert decision is not None
