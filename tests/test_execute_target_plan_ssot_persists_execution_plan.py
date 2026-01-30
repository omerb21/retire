import json
from datetime import date

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
import app.services.llm_chat.chat_stream_orchestration_parts.orchestrator_impl_parts.stream_loop as stream_loop
from app.main import app
from app.models.client import Client
from app.models.scenario import Scenario


def test_execute_target_plan_ssot_persists_execution_plan(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]

    with Session() as db:
        client = db.query(Client).filter(Client.id == 970000001).first()
        if client is None:
            client = Client(
                id=970000001,
                id_number_raw="970000001",
                id_number="970000001",
                full_name="Test User",
                birth_date=date(1980, 1, 1),
            )
            db.add(client)
            db.flush()
        client_id = int(getattr(client, "id", 0) or 0)

        (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "target_pension_plan_data")
            .delete(synchronize_session=False)
        )
        db.commit()

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for deterministic SSOT regression test")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    tool_calls: list[tuple[str, dict]] = []

    def fake_execute_tool_call(tool_name: str, args: dict, client_id: int, db, **kwargs) -> str:
        tool_calls.append((tool_name, args))
        assert tool_name == "BUILD_TARGET_PENSION_PLAN"
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

    resp1 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "חשב תכנית קצבה של 31000 נטו"}],
            "pension_portfolio": [],
        },
    )
    assert resp1.status_code == 200
    assert tool_calls and tool_calls[0][0] == "BUILD_TARGET_PENSION_PLAN"

    with Session() as db:
        row = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "target_pension_plan_data")
            .order_by(Scenario.created_at.desc(), Scenario.id.desc())
            .first()
        )
        assert row is not None
        stored = json.loads(row.parameters)
        res = stored.get("result") if isinstance(stored.get("result"), dict) else {}
        exec_plan = res.get("execution_plan") if isinstance(res.get("execution_plan"), dict) else {}
        accounts = exec_plan.get("accounts") if isinstance(exec_plan.get("accounts"), list) else []
        assert accounts

    resp2 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "בצע תכנית בפועל"}],
            "pension_portfolio": [],
        },
    )
    assert resp2.status_code == 200
    body = resp2.text
    assert "###UI_ACTION###" in body

    ui_raw = body.split("###UI_ACTION###", 1)[1].split("###END_UI_ACTION###", 1)[0]
    ui = json.loads(ui_raw)
    actions = ui.get("actions") if isinstance(ui, dict) else None
    assert isinstance(actions, list) and actions
    first = actions[0]
    assert isinstance(first, dict)
    args = first.get("arguments") if isinstance(first.get("arguments"), dict) else {}

    exec_plan_args = args.get("execution_plan") if isinstance(args.get("execution_plan"), dict) else {}
    exec_plan_accounts = exec_plan_args.get("accounts") if isinstance(exec_plan_args.get("accounts"), list) else []
    assert exec_plan_accounts

    accounts_args = args.get("accounts") if isinstance(args.get("accounts"), list) else []
    assert accounts_args
