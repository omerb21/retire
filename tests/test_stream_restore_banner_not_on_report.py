import json
from datetime import date, datetime, timezone

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app
from app.models.client import Client
from app.models.scenario import Scenario


def test_report_does_not_include_restore_banner(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for REPORT intent")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    with Session() as db:
        client = db.query(Client).filter(Client.id == 930300002).first()
        if client is None:
            client = Client(
                id=930300002,
                id_number_raw="930300002",
                id_number="930300002",
                full_name="Test User",
                birth_date=date(1980, 1, 1),
            )
            db.add(client)
            db.flush()
        client_id = int(getattr(client, "id", 0) or 0)

        params = {
            "pension_portfolio": [],
            "_meta": {
                "operation_type": "restore_snapshot",
                "restored_at_utc": datetime.now(timezone.utc).isoformat(),
                "trace_id": "t_restore",
            },
        }
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
            "messages": [{"role": "user", "content": "דוח"}],
        },
    )
    assert resp.status_code == 200
    body = resp.text

    assert "###UI_ACTION###" in body
    assert "מצב מערכת: שוחזר סנאפסוט" not in body
