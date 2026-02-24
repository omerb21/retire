from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def test_stream_build_target_plan_when_target_is_provided(monkeypatch) -> None:
    def fake_chat_stream(messages, client_id=None):
        raise AssertionError(
            "LLM must not be called for target-plan tools-first routing"
        )

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

    tool_calls: list[str] = []

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
        tool_calls.append(tool_name)
        assert tool_name == "BUILD_TARGET_PENSION_PLAN"
        assert int(float(args.get("target_monthly_pension"))) == 28000
        assert args.get("target_is_net") is True
        return "FAKE_TARGET_PLAN_RESULT"

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
                {"role": "user", "content": "קצבת יעד 28000 נטו - בנה תכנית פרישה"}
            ],
        },
    )

    assert response.status_code == 200
    assert tool_calls == ["BUILD_TARGET_PENSION_PLAN"]
    assert "FAKE_TARGET_PLAN_RESULT" in response.text
