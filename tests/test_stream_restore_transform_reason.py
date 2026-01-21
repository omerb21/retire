import json
from datetime import date, datetime, timezone

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app
from app.models.client import Client
from app.models.scenario import Scenario


def _extract_ui_action_payload(body: str) -> dict:
    assert "###UI_ACTION###" in body
    payload_json = body.split("###UI_ACTION###", 1)[1].split("###END_UI_ACTION###", 1)[0]
    return json.loads(payload_json)


def test_transform_approval_reason_stronger_after_restore_and_replay_is_stable(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for deterministic execute-target-plan")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    calls = {"n": 0}

    def fake_build_transform_accounts_from_target_plan_payload(payload: dict):
        calls["n"] += 1
        if calls["n"] > 1:
            raise AssertionError("accounts builder must not be called on replay")
        return [
            {
                "account_number": "A-001",
                "specific_amounts": {"תגמולי_עובד_אחרי_2000": 1000},
            }
        ]

    monkeypatch.setattr(
        stream_orch,
        "build_transform_accounts_from_target_plan_payload",
        fake_build_transform_accounts_from_target_plan_payload,
    )

    with Session() as db:
        client = db.query(Client).filter(Client.id == 930300003).first()
        if client is None:
            client = Client(
                id=930300003,
                id_number_raw="930300003",
                id_number="930300003",
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

    messages = [
        {
            "role": "assistant",
            "content": "...\n###TARGET_PENSION_PLAN_DATA###\n"
            + json.dumps(
                {
                    "tool_name": "BUILD_TARGET_PENSION_PLAN",
                    "args": {"target_monthly_pension": 28000, "target_is_net": True},
                    "result": {"sources_used": []},
                },
                ensure_ascii=False,
            )
            + "\n###END_TARGET_PENSION_PLAN_DATA###",
        },
        {"role": "user", "content": "בצע את התכנית"},
    ]

    resp1 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": messages,
            "pension_portfolio": [],
        },
    )
    assert resp1.status_code == 200
    body1 = resp1.text
    payload1 = _extract_ui_action_payload(body1)
    actions1 = payload1.get("actions") or []
    assert isinstance(actions1, list) and actions1
    approval1 = actions1[0]
    assert approval1.get("type") == "approval_request"
    assert approval1.get("tool_name") == "TRANSFORM_FUNDS_TO_ASSETS"
    assert (
        approval1.get("reason")
        == "בוצע שחזור סנאפסוט ממש עכשיו. כדי למנוע כפל המרות, ודא שזו הפעולה הנכונה ואז אשר."
    )

    resp2 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": messages,
            "pension_portfolio": [],
        },
    )
    assert resp2.status_code == 200
    body2 = resp2.text
    assert body2 == body1
