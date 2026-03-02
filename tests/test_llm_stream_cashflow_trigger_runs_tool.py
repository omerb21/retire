from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def test_cashflow_trigger_runs_tool(monkeypatch) -> None:
    executed = {"count": 0, "tool_name": None}

    from app.services.llm_chat.chat_stream_orchestration_parts.orchestrator_impl_parts import (
        stream_loop,
    )

    def fake_execute_tool_call(
        tool_name: str,
        tool_args: dict,
        client_id: int,
        db,
        pension_portfolio=None,
        force_max_exemption: bool = False,
        user_approved: bool = True,
        request_id: str | None = None,
    ) -> str:
        raise AssertionError(
            "No tools should be executed for cashflow without an existing plan"
        )

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be used for cashflow calc requests")

    monkeypatch.setattr(stream_loop, "_execute_tool_call", fake_execute_tool_call)
    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "pension_portfolio": [],
            "messages": [{"role": "user", "content": "תחשב לי תזרים פרישה"}],
        },
    )

    assert response.status_code == 200
    body = response.text

    assert executed["count"] == 0

    assert body.strip() == "אין תכנית קיימת להצגת תזרים. יש לבנות תכנית תחילה."
    assert "🔧" not in body
    assert "פלט כלי" not in body
    assert "Tool Error" not in body


def test_cashflow_missing_age_gender_blocks_before_tool(monkeypatch) -> None:
    from app.services.llm_chat.chat_stream_orchestration_parts.orchestrator_impl_parts import (
        stream_loop,
    )

    def fake_execute_tool_call(*args, **kwargs):
        raise AssertionError(
            "No tools should be executed for cashflow without an existing plan"
        )

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be used for deterministic cashflow gating")

    monkeypatch.setattr(stream_loop, "_execute_tool_call", fake_execute_tool_call)
    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "pension_portfolio": [],
            "messages": [
                {
                    "role": "user",
                    "content": "תחשב לי תזרים פרישה יעד נטו: 28000 תאריך פרישה: 2030-01-01",
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.text
    assert body.strip() == "אין תכנית קיימת להצגת תזרים. יש לבנות תכנית תחילה."
    assert "Tool Error" not in body


def test_cashflow_missing_db_and_text_age_gender_blocks_with_short_prompt(
    monkeypatch,
) -> None:
    from app.services.llm_chat.chat_stream_orchestration_parts.orchestrator_impl_parts import (
        stream_loop,
    )

    def fake_execute_tool_call(*args, **kwargs):
        raise AssertionError(
            "Tool must not be executed when DB+text age/gender are missing"
        )

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be used for deterministic cashflow gating")

    monkeypatch.setattr(stream_loop, "_execute_tool_call", fake_execute_tool_call)
    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

    from datetime import date

    from app.database import SessionLocal
    from app.models.client import Client

    db = SessionLocal()
    try:
        client = db.query(Client).filter(Client.id == 1).first()
        if client is not None:
            client.birth_date = date(1970, 1, 1)
            client.gender = None
            db.add(client)
            db.commit()
    finally:
        db.close()

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "pension_portfolio": [],
            "messages": [
                {
                    "role": "user",
                    "content": "תחשב לי תזרים פרישה יעד נטו: 28000",
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.text
    assert "🔧" not in body
    assert "פלט כלי" not in body
    assert "Tool Error" not in body
    assert body.strip() == "אין תכנית קיימת להצגת תזרים. יש לבנות תכנית תחילה."
