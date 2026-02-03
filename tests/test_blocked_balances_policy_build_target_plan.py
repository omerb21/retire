import json
from datetime import date, datetime, timezone

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app
from app.models.client import Client
from app.models.current_employment.employer import CurrentEmployer
from app.models.scenario import Scenario


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
    assert "###UI_ACTION###" in resp2.text
    assert "PROCESS_TERMINATION" in resp2.text

    approval_payload = {"tool_name": "PROCESS_TERMINATION", "arguments": {}}
    resp3 = api.post(
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
    assert resp3.status_code == 200
    assert "עזיבת עבודה" in resp3.text
    assert "בניית תכנית קצבה" in resp3.text
    assert tool_calls == ["PROCESS_TERMINATION", "BUILD_TARGET_PENSION_PLAN"]


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
