import json
from datetime import date

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
import app.services.llm_chat.chat_stream_orchestration_parts.orchestrator_impl_parts.stream_loop as stream_loop
from app.main import app
from app.models.client import Client


def test_stream_cashflow_retirement_date_derived_from_age_75(
    monkeypatch, _test_db
) -> None:
    Session = _test_db["Session"]

    with Session() as db:
        client = db.query(Client).filter(Client.id == 920000002).first()
        if client is None:
            client = Client(
                id=920000002,
                id_number_raw="920000002",
                id_number="920000002",
                full_name="Test User",
                birth_date=date(1953, 4, 16),
                gender="male",
            )
            db.add(client)
            db.flush()
        client_id = int(getattr(client, "id", 0) or 0)
        db.commit()

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError(
            "LLM must not be called for target-net cashflow deterministic routing"
        )

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

    def fake_execute_tool_call(*args, **kwargs) -> str:
        raise AssertionError(
            "No tools should be executed for cashflow without an existing plan"
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
            "client_id": client_id,
            "messages": [
                {
                    "role": "user",
                    "content": "תחשב תזרים פרישה לגיל 75 יעד נטו: 33000",
                }
            ],
            "pension_portfolio": [],
        },
    )

    assert response.status_code == 200
    assert response.text.strip() == "אין תכנית קיימת להצגת תזרים. יש לבנות תכנית תחילה."
