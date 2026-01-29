import json
from datetime import date, datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.models.client import Client
from app.models.scenario import Scenario


def _extract_ui_action_payload(body: str) -> dict:
    start = body.find("###UI_ACTION###")
    end = body.find("###END_UI_ACTION###")
    assert start >= 0
    assert end > start
    return json.loads(body[start + len("###UI_ACTION###") : end])


def test_execute_target_plan_uses_execution_plan_accounts_stream_and_non_stream(_test_db) -> None:
    Session = _test_db["Session"]
    client_id = 960000002

    execution_plan = {
        "accounts": [
            {
                "account_id": "A-001",
                "component": "תגמולי_עובד_אחרי_2000",
                "amount_to_convert": 1000,
                "expected_monthly_pension": 10,
            }
        ],
        "target_gross": 0,
        "target_net": 0,
        "expected_total_gross": 10,
        "expected_total_net": 0,
    }

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

        payload = {
            "tool_name": "BUILD_TARGET_PENSION_PLAN",
            "args": {
                "target_monthly_pension": 30000,
                "target_is_net": True,
                "retirement_age": 67,
                "ignore_blocked_balances": True,
            },
            "result": {
                "execution_plan": execution_plan,
                "sources_used": [],
            },
        }

        db.add(
            Scenario(
                client_id=client_id,
                scenario_name="target_pension_plan_data",
                apply_tax_planning=False,
                apply_capitalization=False,
                apply_exemption_shield=False,
                parameters=json.dumps(payload, ensure_ascii=False),
                created_at=datetime.now(timezone.utc),
            )
        )
        db.commit()

    api = TestClient(app)

    # Non-stream
    resp_ns = api.post(
        "/api/v1/llm/pension-chat",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "בצע את התכנית"}],
            "pension_portfolio": [],
        },
    )
    assert resp_ns.status_code == 200
    body_ns = resp_ns.json().get("reply")
    assert isinstance(body_ns, str)
    assert "###UI_ACTION###" in body_ns
    assert "TRANSFORM_FUNDS_TO_ASSETS" in body_ns
    assert "לא הצלחתי לגזור" not in body_ns

    ui_ns = _extract_ui_action_payload(body_ns)
    actions_ns = ui_ns.get("actions") or []
    assert isinstance(actions_ns, list) and actions_ns
    args_ns = (actions_ns[0] or {}).get("arguments")
    assert isinstance(args_ns, dict)
    assert isinstance(args_ns.get("accounts"), list)
    assert len(args_ns.get("accounts")) > 0

    # Stream
    resp_s = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "בצע את התכנית"}],
            "pension_portfolio": [],
        },
    )
    assert resp_s.status_code == 200
    body_s = resp_s.text
    assert "###UI_ACTION###" in body_s
    assert "TRANSFORM_FUNDS_TO_ASSETS" in body_s
    assert "לא הצלחתי לגזור" not in body_s

    ui_s = _extract_ui_action_payload(body_s)
    actions_s = ui_s.get("actions") or []
    assert isinstance(actions_s, list) and actions_s
    args_s = (actions_s[0] or {}).get("arguments")
    assert isinstance(args_s, dict)
    assert isinstance(args_s.get("accounts"), list)
    assert len(args_s.get("accounts")) > 0
