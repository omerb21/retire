import json

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def test_stream_pending_approval_replay_transform(monkeypatch) -> None:
    def fake_chat_stream(messages, client_id=None):
        raise AssertionError(
            "LLM must not be called for deterministic execute-target-plan"
        )

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

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

    response1 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 777001,
            "messages": messages,
            "pension_portfolio": [],
        },
    )
    assert response1.status_code == 200
    body1 = response1.text
    assert "###UI_ACTION###" in body1
    assert "approval_request" in body1
    assert "TRANSFORM_FUNDS_TO_ASSETS" in body1

    response2 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 777001,
            "messages": messages,
            "pension_portfolio": [],
        },
    )
    assert response2.status_code == 200
    body2 = response2.text
    assert body2 == body1
