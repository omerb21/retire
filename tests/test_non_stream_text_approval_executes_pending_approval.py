import json
from datetime import date

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_orchestration as orch
import app.services.llm_chat.chat_orchestration_helpers as orch_helpers
from app.main import app
from app.models.client import Client
from app.models.scenario import Scenario


def test_non_stream_text_approval_executes_pending_approval(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]

    with Session() as db:
        client = db.query(Client).filter(Client.id == 960000001).first()
        if client is None:
            client = Client(
                id=960000001,
                id_number_raw="960000001",
                id_number="960000001",
                full_name="Test User",
                birth_date=date(1980, 1, 1),
            )
            db.add(client)
            db.flush()
        client_id = int(getattr(client, "id", 0) or 0)

        # Seed a stored target plan payload so execute-target-plan (non-stream) generates an approval_request
        payload = {
            "tool_name": "BUILD_TARGET_PENSION_PLAN",
            "args": {"target_monthly_pension": 31000, "target_is_net": True},
            "result": {"sources_used": []},
        }
        db.query(Scenario).filter(Scenario.client_id == client_id).filter(
            Scenario.scenario_name.in_(["target_pension_plan_data", "pending_approval"])
        ).delete(synchronize_session=False)
        db.flush()
        db.add(
            Scenario(
                client_id=client_id,
                scenario_name="target_pension_plan_data",
                apply_tax_planning=False,
                apply_capitalization=False,
                apply_exemption_shield=False,
                parameters=json.dumps(payload, ensure_ascii=False),
            )
        )
        db.commit()

    def fake_build_transform_accounts_from_target_plan_payload(_payload: dict):
        return [
            {
                "account_number": "A-001",
                "specific_amounts": {"תגמולי_עובד_אחרי_2000": 1000},
            }
        ]

    monkeypatch.setattr(
        orch_helpers,
        "build_transform_accounts_from_target_plan_payload",
        fake_build_transform_accounts_from_target_plan_payload,
    )

    def fake_chat(messages, client_id=None):
        raise AssertionError("LLM must not be called for deterministic approval execution")

    monkeypatch.setattr(orch.pension_llm_service, "chat", fake_chat)

    tool_calls: list[tuple[str, dict, bool]] = []

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
        tool_calls.append((tool_name, args if isinstance(args, dict) else {}, bool(user_approved)))
        assert tool_name != "RUN_RETIREMENT_CASHFLOW_ANALYSIS"
        if tool_name == "TRANSFORM_FUNDS_TO_ASSETS":
            assert user_approved is True
            return json.dumps({"success": True, "total_converted": 1}, ensure_ascii=False)
        return json.dumps({"success": True}, ensure_ascii=False)

    monkeypatch.setattr(orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)

    # Step 1: request execute-target-plan in non-stream -> should create pending_approval in DB and return UI action
    resp1 = api.post(
        "/api/v1/llm/pension-chat",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "בצע תכנית בפועל"}],
            "pension_portfolio": [],
        },
    )
    assert resp1.status_code == 200
    assert "###UI_ACTION###" in resp1.json()["reply"]
    assert "approval_request" in resp1.json()["reply"]

    # Step 2: approve by text -> must execute pending approval immediately
    resp2 = api.post(
        "/api/v1/llm/pension-chat",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "מאשר"}],
            "pension_portfolio": [],
        },
    )
    assert resp2.status_code == 200

    assert any(c[0] == "TRANSFORM_FUNDS_TO_ASSETS" and c[2] is True for c in tool_calls)

    with Session() as db:
        pending = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "pending_approval")
            .order_by(Scenario.created_at.desc())
            .first()
        )
        assert pending is None
