import json
from datetime import date

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app
from app.models.client import Client
from app.models.scenario import Scenario


def _extract_ui_action_payload(body: str) -> dict:
    assert "###UI_ACTION###" in body
    payload_json = body.split("###UI_ACTION###", 1)[1].split("###END_UI_ACTION###", 1)[0]
    return json.loads(payload_json)


def test_stream_restore_snapshot_requires_approval(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]
    with Session() as db:
        client = db.query(Client).filter(Client.id == 910100001).first()
        if client is None:
            client = Client(
                id=910100001,
                id_number_raw="910100001",
                id_number="910100001",
                full_name="Test User",
                birth_date=date(1980, 1, 1),
            )
            db.add(client)
            db.commit()
        client_id = int(getattr(client, "id", 0) or 0)

        snapshot = Scenario(
            client_id=client_id,
            scenario_name="pension_portfolio_snapshot",
            apply_tax_planning=False,
            apply_capitalization=False,
            apply_exemption_shield=False,
            parameters=json.dumps({"pension_portfolio": [{"account_number": "A", "balance": 1.0}]}, ensure_ascii=False),
        )
        db.add(snapshot)
        db.commit()
        snapshot_id = int(getattr(snapshot, "id", 0) or 0)

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for deterministic restore snapshot flow")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "שחזר תיק"}],
        },
    )

    assert response.status_code == 200
    body = response.text
    payload = _extract_ui_action_payload(body)

    assert payload.get("type") == "ui_actions"
    actions = payload.get("actions") or []
    assert isinstance(actions, list) and actions

    approval = actions[0]
    assert approval.get("type") == "approval_request"
    assert approval.get("tool_name") == "RESTORE_PENSION_PORTFOLIO_SNAPSHOT"
    assert approval.get("arguments", {}).get("snapshot_scenario_id") == snapshot_id
    assert approval.get("arguments", {}).get("safety_mode") == "strict"
    assert approval.get("risk_level") == "high"
