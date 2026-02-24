from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def test_stream_plan_request_without_target_prompts_for_target(monkeypatch) -> None:
    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for plan request without target")

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
        raise AssertionError(
            "No tool should be executed for plan request without target"
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
            "messages": [{"role": "user", "content": "בנה תכנית פרישה"}],
        },
    )

    assert response.status_code == 200
    body = response.text
    assert "🔧" not in body
    assert "###UI_ACTION###" not in body
    assert "צריך יעד חודשי נטו" in body
    assert "יעד הכנסה (נטו): 15,000" not in body
