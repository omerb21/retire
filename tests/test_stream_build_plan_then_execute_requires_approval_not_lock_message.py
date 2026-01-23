import json

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app
from app.models.scenario import Scenario


def test_stream_build_plan_then_execute_requires_approval_not_lock_message(monkeypatch, _test_db) -> None:
    """Regression: BUILD_TARGET_PENSION_PLAN must not trigger post-conversion lock messaging.

    We simulate a client that is "locked" only via snapshot _meta.operation_type,
    but with no conversion assets. Then we ask to execute the plan: we should
    get an approval_request UI action, not "מצב תיק לאחר המרה".
    """

    Session = _test_db["Session"]

    client_id = 930000001

    with Session() as db:
        # Seed a snapshot whose meta indicates conversion-like operation, without creating any conversion assets.
        snap = Scenario(
            client_id=client_id,
            scenario_name="pension_portfolio_snapshot",
            apply_tax_planning=False,
            apply_capitalization=False,
            apply_exemption_shield=False,
            parameters=json.dumps({"pension_portfolio": [], "_meta": {"operation_type": "TRANSFORM_FUNDS_TO_ASSETS"}}, ensure_ascii=False),
        )
        db.add(snap)
        db.commit()

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for deterministic execute-target-plan")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    calls = {"n": 0}

    def fake_build_transform_accounts_from_target_plan_payload(payload: dict):
        calls["n"] += 1
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

    api = TestClient(app)

    messages = [
        {
            "role": "assistant",
            "content": "...\n###TARGET_PENSION_PLAN_DATA###\n"
            + json.dumps(
                {
                    "tool_name": "BUILD_TARGET_PENSION_PLAN",
                    "args": {"target_monthly_pension": 31000, "target_is_net": True},
                    "result": {"sources_used": []},
                },
                ensure_ascii=False,
            )
            + "\n###END_TARGET_PENSION_PLAN_DATA###",
        },
        {"role": "user", "content": "בצע את התכנית בפועל"},
    ]

    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": messages,
            "pension_portfolio": [],
        },
    )

    assert response.status_code == 200
    body = response.text
    assert "###UI_ACTION###" in body
    assert "approval_request" in body
    assert "TRANSFORM_FUNDS_TO_ASSETS" in body
    assert "כותרת: מצב תיק לאחר המרה" not in body
    assert "כותרת: תכנית לאחר המרה" not in body
