from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def test_stream_orchestration_plan_cashflow_only_runs_tool_once_no_llm(
    monkeypatch,
) -> None:
    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for cashflow-only orchestration")

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

    def fake_execute_tool_call(*args, **kwargs):
        raise AssertionError(
            "No tools should be executed for cashflow-only when no plan exists"
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
                    "content": "תחשב לי תזרים פרישה יעד נטו: 28000 תאריך פרישה: 2030-01-01 גבר בן 67",
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.text

    assert body.strip() == "אין תכנית קיימת להצגת תזרים. יש לבנות תכנית תחילה."
    assert "🔧" not in body
    assert "פלט כלי" not in body
    assert "###UI_ACTION###" not in body
