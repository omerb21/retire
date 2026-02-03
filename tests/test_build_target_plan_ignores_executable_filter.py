import json
from datetime import date, datetime, timezone

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app
from app.models.client import Client
from app.models.scenario import Scenario


def test_build_target_plan_ignores_executable_filter(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]

    client_id = 995000777

    with Session() as db:
        client = db.query(Client).filter(Client.id == client_id).first()
        if client is None:
            client = Client(
                id=client_id,
                id_number_raw=str(client_id),
                id_number=str(client_id),
                full_name="Test User",
                birth_date=date(1980, 1, 1),
                gender="male",
                is_active=True,
            )
            db.add(client)
            db.flush()

        # Snapshot is intentionally shaped so that only nested 'components' carries the money.
        # This used to be missed by BUILD_TARGET_PENSION_PLAN snapshot detection.
        snapshot_accounts = [
            {
                "מספר_חשבון": "X1",
                "שם_תכנית": "Fund X",
                "חברה_מנהלת": "X",
                "סוג_מוצר": "קופת גמל",
                "balance": 0,
                "components": {
                    "פיצויים_מעסיק_נוכחי": 100000,
                },
            }
        ]
        db.add(
            Scenario(
                client_id=client_id,
                scenario_name="pension_portfolio_snapshot",
                apply_tax_planning=False,
                apply_capitalization=False,
                apply_exemption_shield=False,
                parameters=json.dumps({"pension_portfolio": snapshot_accounts}, ensure_ascii=False),
                created_at=datetime.now(timezone.utc),
            )
        )
        db.commit()

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for deterministic plan phrase request")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    api = TestClient(app)

    resp = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "יעד נטו: 30000"}],
            "pension_portfolio": [],
        },
    )

    assert resp.status_code == 200
    # Core regression assertion: BUILD must not talk about executability.
    assert "אין מספיק מקורות ניתנים לביצוע" not in resp.text
    # And it must also not claim there are no sources.
    assert "לא נמצאו מקורות קצבה" not in resp.text
    # No approvals should be created during BUILD.
    assert "###UI_ACTION###" not in resp.text
    assert "approval_request" not in resp.text

    with Session() as db:
        pending = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "pending_approval")
            .order_by(Scenario.created_at.desc())
            .first()
        )
        assert pending is None
