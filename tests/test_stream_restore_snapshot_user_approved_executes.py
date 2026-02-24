import json
from datetime import date

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app
from app.models.client import Client
from app.models.scenario import Scenario


def _extract_ui_action_payload(body: str) -> dict:
    assert "###UI_ACTION###" in body
    payload_json = body.split("###UI_ACTION###", 1)[1].split("###END_UI_ACTION###", 1)[
        0
    ]
    return json.loads(payload_json)


def test_stream_restore_snapshot_user_approved_executes(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]
    with Session() as db:
        client = db.query(Client).filter(Client.id == 910100002).first()
        if client is None:
            client = Client(
                id=910100002,
                id_number_raw="910100002",
                id_number="910100002",
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
            parameters=json.dumps(
                {"pension_portfolio": [{"account_number": "A", "balance": 1.0}]},
                ensure_ascii=False,
            ),
        )
        db.add(snapshot)
        db.commit()
        snapshot_id = int(getattr(snapshot, "id", 0) or 0)

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError(
            "LLM must not be called for deterministic restore snapshot flow"
        )

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

    tool_calls: list[tuple[str, dict]] = []

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
        tool_calls.append((tool_name, args))
        assert user_approved is True
        if tool_name == "RESTORE_PENSION_PORTFOLIO_SNAPSHOT":
            assert args.get("snapshot_scenario_id") == snapshot_id
            assert args.get("safety_mode") == "strict"
            return json.dumps(
                {
                    "success": True,
                    "restored_snapshot_scenario_id": 999,
                    "previous_snapshot_scenario_id": 888,
                    "message": "ok",
                },
                ensure_ascii=False,
            )
        raise AssertionError(f"Unexpected tool call: {tool_name}")

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)

    first = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "שחזר תיק"}],
        },
    )
    assert first.status_code == 200
    body1 = first.text
    payload = _extract_ui_action_payload(body1)
    assert (
        payload.get("actions")[0].get("tool_name")
        == "RESTORE_PENSION_PORTFOLIO_SNAPSHOT"
    )

    second = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [
                {
                    "role": "user",
                    "content": f'###USER_APPROVED### {{"tool_name": "RESTORE_PENSION_PORTFOLIO_SNAPSHOT", "arguments": {{"snapshot_scenario_id": {snapshot_id}, "safety_mode": "strict"}}}}',
                }
            ],
        },
    )

    assert second.status_code == 200
    body2 = second.text
    assert "🔧" in body2
    assert "נדרש אישור" not in body2

    assert tool_calls[0][0] == "RESTORE_PENSION_PORTFOLIO_SNAPSHOT"
