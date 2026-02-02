import json

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app
from app.models.client import Client
from app.models.scenario import Scenario


def test_stream_user_approved_system_snapshot_returns_structured_payload(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for user-approved GET_SYSTEM_STATE_SNAPSHOT")

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
        assert tool_name == "GET_SYSTEM_STATE_SNAPSHOT"
        assert isinstance(args, dict)
        assert user_approved is True
        assert client_id == 1
        return json.dumps(
            {
                "service": {"name": "retire", "version": "1.2.3", "time_utc": "2026-01-01T00:00:00Z"},
                "db": {
                    "ok": True,
                    "counts": {
                        "clients": 12,
                        "pension_funds": 6,
                        "capital_assets": 8,
                        "pension_portfolio_snapshots": 9,
                    },
                },
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    with Session() as db:
        client = db.query(Client).filter(Client.id == 1).first()
        if client is None:
            client = Client(id=1, id_number_raw="1", id_number="1", full_name="Test User")
            db.add(client)
            db.flush()
        db.add(
            Scenario(
                client_id=1,
                scenario_name="pending_approval",
                apply_tax_planning=False,
                apply_capitalization=False,
                apply_exemption_shield=False,
                parameters=json.dumps(
                    {"tool_name": "GET_SYSTEM_STATE_SNAPSHOT", "arguments": {}},
                    ensure_ascii=False,
                ),
            )
        )
        db.commit()

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [
                {
                    "role": "user",
                    "content": '###USER_APPROVED### {"tool_name":"GET_SYSTEM_STATE_SNAPSHOT","arguments":{}}',
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.text

    assert "🔧" in body
    assert "GET_SYSTEM_STATE_SNAPSHOT" in body
    assert '"service"' in body
    assert '"db"' in body
    assert '"counts"' in body

    assert "ניתוח פרישה – עיקרי התוצאות" not in body
