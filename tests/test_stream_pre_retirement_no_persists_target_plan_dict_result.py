import json
from datetime import date

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
import app.services.llm_chat.chat_stream_orchestration_parts.orchestrator_impl_parts.stream_loop as stream_loop
from app.main import app
from app.models.client import Client
from app.models.scenario import Scenario


def test_stream_pre_retirement_no_persists_target_plan_dict_result(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]

    with Session() as db:
        client = db.query(Client).filter(Client.id == 970000002).first()
        if client is None:
            client = Client(
                id=970000002,
                id_number_raw="970000002",
                id_number="970000002",
                full_name="Test User 2",
                birth_date=date(1980, 1, 1),
            )
            db.add(client)
            db.flush()
        client_id = int(getattr(client, "id", 0) or 0)

        (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(
                Scenario.scenario_name.in_(
                    [
                        "target_pension_plan_data",
                        "target_pension_plan",
                        "pending_plan_target",
                        "pending_approval",
                        "pending_pre_retirement_plan_resolution",
                    ]
                )
            )
            .delete(synchronize_session=False)
        )

        db.add(
            Scenario(
                client_id=client_id,
                scenario_name="pending_plan_target",
                apply_tax_planning=False,
                apply_capitalization=False,
                apply_exemption_shield=False,
                parameters=json.dumps({"active": True}, ensure_ascii=False),
            )
        )
        db.add(
            Scenario(
                client_id=client_id,
                scenario_name="pending_approval",
                apply_tax_planning=False,
                apply_capitalization=False,
                apply_exemption_shield=False,
                parameters=json.dumps({"tool_name": "X", "arguments": {}}, ensure_ascii=False),
            )
        )

        db.add(
            Scenario(
                client_id=client_id,
                scenario_name="pension_portfolio_snapshot",
                apply_tax_planning=False,
                apply_capitalization=False,
                apply_exemption_shield=False,
                parameters=json.dumps(
                    {
                        "pension_portfolio": [
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
                    },
                    ensure_ascii=False,
                ),
            )
        )
        db.commit()

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for deterministic stream regression test")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    tool_calls: list[tuple[str, dict]] = []

    def fake_execute_tool_call(tool_name: str, args: dict, client_id: int, db, **kwargs):
        tool_calls.append((tool_name, args))
        assert tool_name == "BUILD_TARGET_PENSION_PLAN"
        return {
            "success": True,
            "tool_name": "BUILD_TARGET_PENSION_PLAN",
            "args": args,
            "result": {
                "target_achieved": True,
                "plan_steps": [{"step_number": 1}],
                "sources_used": [
                    {
                        "source_type": "pension_fund_from_portfolio",
                        "account_number": "A-001",
                        "component_field": "תגמולי_עובד_אחרי_2000",
                        "balance_used": 1000,
                        "pension_used": 10,
                    }
                ],
                "execution_plan": {
                    "accounts": [],
                    "target_gross": 0,
                    "target_net": 0,
                    "expected_total_gross": 0,
                    "expected_total_net": 0,
                },
            },
        }

    monkeypatch.setattr(stream_loop, "_execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)

    # 1) execute -> should ask blocked balances question (execute-only)
    resp1 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "בצע תכנית בפועל"}],
            "pension_portfolio": [],
        },
    )
    assert resp1.status_code == 200
    assert not tool_calls
    assert "האם לכלול" in resp1.text

    with Session() as db:
        pending_row = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "pending_pre_retirement_plan_resolution")
            .order_by(Scenario.created_at.desc(), Scenario.id.desc())
            .first()
        )
        assert pending_row is not None

        pending_plan_target_count_before = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "pending_plan_target")
            .count()
        )
        assert pending_plan_target_count_before == 1

        pending_approval_count_before = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "pending_approval")
            .count()
        )
        assert pending_approval_count_before == 1

    # 2) answer no -> must clear pending + persist decision; must NOT execute tools
    resp2 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "לא"}],
            "pension_portfolio": [],
        },
    )
    assert resp2.status_code == 200
    assert not tool_calls
    assert "לא נכלול יתרות חסומות" in resp2.text

    with Session() as db:
        decision_row = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "ignore_blocked_balances_decision")
            .order_by(Scenario.created_at.desc(), Scenario.id.desc())
            .first()
        )
        assert decision_row is not None

        pending_plan_target_count_after = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "pending_plan_target")
            .count()
        )
        assert pending_plan_target_count_after == 1

        pending_approval_count_after = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "pending_approval")
            .count()
        )
        assert pending_approval_count_after == 1

        pending_pre_retirement_count_after = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "pending_pre_retirement_plan_resolution")
            .count()
        )
        assert pending_pre_retirement_count_after == 0
