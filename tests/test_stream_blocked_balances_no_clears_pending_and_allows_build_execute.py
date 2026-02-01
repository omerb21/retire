import json
from datetime import date, datetime, timezone

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.services.llm_agent_tools_service import AgentToolsService
from app.main import app
from app.models.client import Client
from app.models.scenario import Scenario


def test_stream_blocked_balances_no_clears_pending_and_allows_build_execute(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]
    client_id = 995000001

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
                    "pending_pre_retirement_plan_resolution",
                    "ignore_blocked_balances_decision",
                    "target_pension_plan",
                    "target_pension_plan_data",
                ]
            )
        ).delete(synchronize_session=False)

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
        raise AssertionError("LLM must not be called for deterministic blocked-balances regression test")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    def fake_build_target_pension_plan(
        self,
        target_monthly_pension,
        target_is_net,
        retirement_age=None,
        ignore_blocked_balances=True,
    ):
        return {
            "success": True,
            "tool_name": "BUILD_TARGET_PENSION_PLAN",
            "result": {
                "target_achieved": True,
                "plan_steps": [{"step_number": 1}],
                "sources_used": [
                    {
                        "source_type": "pension_fund_from_portfolio",
                        "account_number": "B1",
                        "component_field": "תגמולי_עובד_אחרי_2000",
                        "balance_used": 1000,
                        "pension_used": 10,
                    }
                ],
                "execution_plan": {
                    "accounts": [
                        {
                            "account_number": "B1",
                            "component_field": "תגמולי_עובד_אחרי_2000",
                            "amount": 1000,
                        }
                    ],
                    "target_gross": 0,
                    "target_net": 0,
                    "expected_total_gross": 0,
                    "expected_total_net": 0,
                },
            },
            "explanation": "OK",
        }

    monkeypatch.setattr(AgentToolsService, "build_target_pension_plan", fake_build_target_pension_plan)

    api = TestClient(app)

    # 1) build -> should ask blocked balances
    resp1 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "בנה תכנית יעד קצבה יעד נטו 30000"}],
            "pension_portfolio": [],
        },
    )
    assert resp1.status_code == 200
    assert "האם לכלול" in resp1.text

    # 2) answer no with punctuation -> must clear pending + persist decision + build plan
    resp2 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "לא."}],
            "pension_portfolio": [],
        },
    )
    assert resp2.status_code == 200
    assert "בניית תכנית קצבה" in resp2.text

    with Session() as db:
        pending = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "pending_pre_retirement_plan_resolution")
            .order_by(Scenario.created_at.desc())
            .first()
        )
        assert pending is None
        decision = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "ignore_blocked_balances_decision")
            .order_by(Scenario.created_at.desc())
            .first()
        )
        assert decision is not None

    # 3) build again -> must NOT ask again
    resp3 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "בנה תכנית יעד קצבה יעד נטו 30000"}],
            "pension_portfolio": [],
        },
    )
    assert resp3.status_code == 200
    assert "האם לכלול" not in resp3.text

    # 4) execute -> must return UI action (approval request) and not the failure text
    resp4 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "בצע תכנית בפועל"}],
            "pension_portfolio": [],
        },
    )
    assert resp4.status_code == 200
    assert "###UI_ACTION###" in resp4.text
    assert "לא הצלחתי לגזור" not in resp4.text
