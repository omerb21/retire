import json
from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
import app.services.llm_chat.chat_stream_orchestration_parts.orchestrator_impl_parts.stream_loop as stream_loop
from app.main import app
from app.models.client import Client
from app.models.scenario import Scenario


def test_stream_pending_plan_target_marker_blocks_cashflow(
    monkeypatch, _test_db
) -> None:
    Session = _test_db["Session"]

    with Session() as db:
        client = db.query(Client).filter(Client.id == 950000003).first()
        if client is None:
            client = Client(
                id=950000003,
                id_number_raw="950000003",
                id_number="950000003",
                full_name="Test User",
                birth_date=date(1980, 1, 1),
            )
            db.add(client)
            db.flush()
        client_id = int(getattr(client, "id", 0) or 0)

        now = datetime.now(timezone.utc)
        payload = {
            "kind": "pending_plan_target",
            "active": True,
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(minutes=5)).isoformat(),
            "_meta": {"source": "test"},
        }
        db.query(Scenario).filter(Scenario.client_id == client_id).filter(
            Scenario.scenario_name == "pending_plan_target"
        ).delete(synchronize_session=False)
        db.flush()
        db.add(
            Scenario(
                client_id=client_id,
                scenario_name="pending_plan_target",
                apply_tax_planning=False,
                apply_capitalization=False,
                apply_exemption_shield=False,
                parameters=json.dumps(payload, ensure_ascii=False),
            )
        )
        db.commit()

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError(
            "LLM must not be called for pending_plan_target deterministic routing"
        )

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

    tool_calls: list[tuple[str, dict]] = []

    def fake_execute_tool_call(
        tool_name: str, args: dict, client_id: int, db, **kwargs
    ) -> str:
        tool_calls.append((tool_name, args))
        assert tool_name != "RUN_RETIREMENT_CASHFLOW_ANALYSIS"
        assert tool_name == "BUILD_TARGET_PENSION_PLAN"
        payload = {
            "tool_name": "BUILD_TARGET_PENSION_PLAN",
            "args": args,
            "result": {"sources_used": []},
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
            "messages": [{"role": "user", "content": "יעד נטו 31000"}],
            "pension_portfolio": [],
        },
    )

    assert resp.status_code == 200
    assert tool_calls and tool_calls[0][0] == "BUILD_TARGET_PENSION_PLAN"
    assert "דוח תזרים" not in resp.text
