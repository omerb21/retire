import json
from datetime import date, datetime, timezone

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
import app.services.llm_chat.chat_stream_orchestration_parts.orchestrator_impl_parts.stream_loop as stream_loop
from app.main import app
from app.models.client import Client
from app.models.scenario import Scenario


def test_stream_build_target_plan_skips_empty_snapshot_models_loader(
    monkeypatch, _test_db
) -> None:
    Session = _test_db["Session"]

    with Session() as db:
        client = db.query(Client).filter(Client.id == 990000001).first()
        if client is None:
            client = Client(
                id=990000001,
                id_number_raw="990000001",
                id_number="990000001",
                full_name="Test User",
                birth_date=date(1980, 1, 1),
            )
            db.add(client)
            db.flush()
        client_id = int(getattr(client, "id", 0) or 0)

        (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "pension_portfolio_snapshot")
            .delete(synchronize_session=False)
        )
        db.commit()

        prev_snapshot = Scenario(
            client_id=client_id,
            scenario_name="pension_portfolio_snapshot",
            apply_tax_planning=False,
            apply_capitalization=False,
            apply_exemption_shield=False,
            parameters=json.dumps(
                {
                    "pension_portfolio": [
                        {
                            "מספר_חשבון": "A-001",
                            "שם_תכנית": "Plan A",
                            "סוג_מוצר": "קופת גמל",
                            "יתרה": 1234,
                        }
                    ],
                    "_meta": {"operation_type": ""},
                },
                ensure_ascii=False,
            ),
            created_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        )

        newest_empty = Scenario(
            client_id=client_id,
            scenario_name="pension_portfolio_snapshot",
            apply_tax_planning=False,
            apply_capitalization=False,
            apply_exemption_shield=False,
            parameters=json.dumps(
                {
                    "pension_portfolio": [{"שם_תכנית": "Empty", "יתרה": 0}],
                    "_meta": {"operation_type": ""},
                },
                ensure_ascii=False,
            ),
            created_at=datetime(2026, 1, 1, 12, 5, 0, tzinfo=timezone.utc),
        )

        db.add(prev_snapshot)
        db.add(newest_empty)
        db.commit()

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError(
            "LLM must not be called for deterministic stream regression test"
        )

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

    tool_calls: list[tuple[str, dict]] = []

    def fake_execute_tool_call(
        tool_name: str, args: dict, client_id: int, db, pension_portfolio=None, **kwargs
    ) -> str:
        tool_calls.append((tool_name, args))
        assert tool_name == "BUILD_TARGET_PENSION_PLAN"
        assert pension_portfolio is not None
        assert isinstance(pension_portfolio, list)
        assert pension_portfolio

        has_value = False
        for acc in pension_portfolio:
            bal = getattr(acc, "יתרה", None)
            if isinstance(bal, (int, float)) and float(bal) > 0:
                has_value = True
                break
        assert has_value

        payload = {
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
        return (
            "OK\n\n###TARGET_PENSION_PLAN_DATA###\n"
            + json.dumps(payload, ensure_ascii=False)
            + "\n###END_TARGET_PENSION_PLAN_DATA###"
        )

    monkeypatch.setattr(stream_loop, "_execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    resp = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "חשב תכנית קצבה של 30000 נטו"}],
            "pension_portfolio": [],
        },
    )
    assert resp.status_code == 200
    assert tool_calls and tool_calls[0][0] == "BUILD_TARGET_PENSION_PLAN"
