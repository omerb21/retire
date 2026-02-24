import json
from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app
from app.models.client import Client
from app.models.scenario import Scenario


def test_stream_restore_banner_shown_for_2_minutes_non_report(
    monkeypatch, _test_db
) -> None:
    Session = _test_db["Session"]

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError(
            "LLM must not be called for deterministic data awareness flow"
        )

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

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
        if tool_name == "GET_SYSTEM_STATE_SNAPSHOT":
            return json.dumps(
                {"generated_at": "now", "counts": {}, "entities": {}},
                ensure_ascii=False,
            )
        raise AssertionError(f"Unexpected tool call: {tool_name}")

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

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

        restore_meta = {
            "operation_type": "restore_snapshot",
            "restored_at_utc": datetime.now(timezone.utc).isoformat(),
            "trace_id": "t_restore",
        }
        params = {"pension_portfolio": [], "_meta": restore_meta}
        snap = Scenario(
            client_id=client_id,
            scenario_name="pension_portfolio_snapshot",
            apply_tax_planning=False,
            apply_capitalization=False,
            apply_exemption_shield=False,
            parameters=json.dumps(params, ensure_ascii=False),
        )
        db.add(snap)
        db.commit()

    api = TestClient(app)
    resp = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "האם אתה מודע לכל הנתונים שלי?"}],
        },
    )
    assert resp.status_code == 200
    body = resp.text
    assert (
        "מצב מערכת: שוחזר סנאפסוט (restore_snapshot). אפשר להמשיך לתכנית/תרחיש." in body
    )

    # Expired banner should not show (simulate old restore)
    with Session() as db:
        old_meta = dict(restore_meta)
        old_meta["restored_at_utc"] = (
            datetime.now(timezone.utc) - timedelta(seconds=121)
        ).isoformat()
        old_params = {"pension_portfolio": [], "_meta": old_meta}
        snap2 = Scenario(
            client_id=client_id,
            scenario_name="pension_portfolio_snapshot",
            apply_tax_planning=False,
            apply_capitalization=False,
            apply_exemption_shield=False,
            parameters=json.dumps(old_params, ensure_ascii=False),
        )
        db.add(snap2)
        db.commit()

    resp2 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "האם אתה מודע לכל הנתונים שלי?"}],
        },
    )
    assert resp2.status_code == 200
    body2 = resp2.text
    assert (
        "מצב מערכת: שוחזר סנאפסוט (restore_snapshot). אפשר להמשיך לתכנית/תרחיש."
        not in body2
    )
