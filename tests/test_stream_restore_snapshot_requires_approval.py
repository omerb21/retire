import json
from datetime import date

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app
from app.models.client import Client


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

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for deterministic restore snapshot flow")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

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
        assert user_approved is True
        if tool_name == "GET_PENSION_PORTFOLIO_SNAPSHOT_HISTORY":
            history = [
                {
                    "scenario_id": 222,
                    "created_at": "2026-01-01T00:00:00Z",
                    "meta": {"operation_type": "pension_portfolio_upload"},
                    "estimated_nonzero_balance_rows": 3,
                },
                {
                    "scenario_id": 111,
                    "created_at": "2026-01-02T00:00:00Z",
                    "meta": {"operation_type": "TRANSFORM_FUNDS_TO_ASSETS"},
                    "estimated_nonzero_balance_rows": 0,
                },
            ]
            return json.dumps(history, ensure_ascii=False)
        raise AssertionError(f"Unexpected tool call: {tool_name}")

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

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
    assert approval.get("arguments", {}).get("snapshot_scenario_id") == 222
    assert approval.get("arguments", {}).get("safety_mode") == "strict"
    assert approval.get("risk_level") == "high"
