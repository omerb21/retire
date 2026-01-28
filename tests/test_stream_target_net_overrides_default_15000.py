import json

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def test_stream_target_net_overrides_default_15000(monkeypatch) -> None:
    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for target-net cashflow routing")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    def fake_execute_tool_call(*args, **kwargs) -> str:
        raise AssertionError("No tools should be executed for cashflow without an existing plan")

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
    assert response.text.strip() == "אין תכנית קיימת להצגת תזרים. יש לבנות תכנית תחילה."
