import json

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def test_stream_target_net_overrides_default_15000(monkeypatch) -> None:
    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for target-net cashflow routing")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    seen_args: list[dict] = []

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
        assert tool_name == "RUN_RETIREMENT_CASHFLOW_ANALYSIS"
        seen_args.append(args)
        return json.dumps(
            {
                "success": True,
                "tool_name": tool_name,
                "result": {"desired_monthly_income": args.get("desired_monthly_income")},
                "explanation": "🎯 **יעד הכנסה (נטו):** 28000 ₪",
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    def fake_load_latest_pension_portfolio_snapshot_models(db, client_id):
        return None

    monkeypatch.setattr(
        stream_orch,
        "load_latest_pension_portfolio_snapshot_models",
        fake_load_latest_pension_portfolio_snapshot_models,
    )

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [
                {
                    "role": "user",
                    "content": "יעד נטו 28000 תאריך פרישה: 2030-01-01 אישה בת 62",
                }
            ],
        },
    )

    assert response.status_code == 200
    assert seen_args
    assert int(float(seen_args[0].get("desired_net_monthly_income"))) == 28000
    assert "28000" in response.text
    assert "15000" not in response.text
