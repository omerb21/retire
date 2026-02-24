import json
from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app
from app.models.client import Client
from app.models.scenario import Scenario


def test_stream_pending_plan_target_expired_reprompts_and_no_tool(
    monkeypatch, _test_db
) -> None:
    Session = _test_db["Session"]

    with Session() as db:
        client = db.query(Client).filter(Client.id == 910000002).first()
        if client is None:
            client = Client(
                id=910000002,
                id_number_raw="910000002",
                id_number="910000002",
                full_name="Test User",
                birth_date=date(1980, 1, 1),
            )
            db.add(client)
            db.flush()
        client_id = int(getattr(client, "id", 0) or 0)

        now = datetime.now(timezone.utc)
        payload = {
            "kind": "pending_plan_target",
            "created_at": (now - timedelta(minutes=10)).isoformat(),
            "expires_at": (now - timedelta(seconds=5)).isoformat(),
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
            "LLM must not be called for expired pending_plan_target reprompt"
        )

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

    def fake_execute_tool_call(*args, **kwargs) -> str:
        raise AssertionError(
            "No tool must be executed when pending_plan_target is expired"
        )

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    resp = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "31000"}],
            "pension_portfolio": [],
        },
    )

    assert resp.status_code == 200
    assert "כתוב: יעד נטו" in resp.text
    assert "🔧" not in resp.text
