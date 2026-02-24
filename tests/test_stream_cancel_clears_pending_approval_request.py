import json
from datetime import date

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app
from app.models.client import Client
from app.models.scenario import Scenario
from app.services.llm_chat.chat_orchestration_helpers import (
    load_pending_approval_request,
    store_pending_approval_request,
)


def test_stream_cancel_clears_pending_approval_request(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for deterministic cancel flow")

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

    with Session() as db:
        client = db.query(Client).filter(Client.id == 930300001).first()
        if client is None:
            client = Client(
                id=930300001,
                id_number_raw="930300001",
                id_number="930300001",
                full_name="Test User",
                birth_date=date(1980, 1, 1),
            )
            db.add(client)
            db.flush()
        client_id = int(getattr(client, "id", 0) or 0)

        # Ensure a snapshot exists so restore approval can be valid.
        db.query(Scenario).filter(Scenario.client_id == client_id).filter(
            Scenario.scenario_name == "pension_portfolio_snapshot"
        ).delete(synchronize_session=False)
        snapshot = Scenario(
            client_id=client_id,
            scenario_name="pension_portfolio_snapshot",
            apply_tax_planning=False,
            apply_capitalization=False,
            apply_exemption_shield=False,
            parameters=json.dumps({"pension_portfolio": []}, ensure_ascii=False),
        )
        db.add(snapshot)
        db.flush()
        snapshot_id = int(getattr(snapshot, "id", 0) or 0)

        # Create a pending approval request in DB
        restore_args = {"snapshot_scenario_id": snapshot_id, "safety_mode": "strict"}
        assert (
            store_pending_approval_request(
                db=db,
                client_id=client_id,
                tool_name="RESTORE_PENSION_PORTFOLIO_SNAPSHOT",
                tool_args=restore_args,
            )
            is True
        )
        db.commit()

    api = TestClient(app)
    resp = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [
                {
                    "role": "user",
                    "content": f'###USER_CANCELLED### {json.dumps({"tool_name": "RESTORE_PENSION_PORTFOLIO_SNAPSHOT", "arguments": restore_args}, ensure_ascii=False)}',
                }
            ],
        },
    )

    assert resp.status_code == 200
    assert "לא בוצע שינוי במערכת" in resp.text

    with Session() as db:
        pending = load_pending_approval_request(db=db, client_id=client_id)
        assert pending is None
