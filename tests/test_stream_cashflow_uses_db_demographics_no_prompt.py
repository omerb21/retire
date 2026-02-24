import json
from datetime import date

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
import app.services.llm_chat.chat_stream_orchestration_parts.orchestrator_impl_parts.stream_loop as stream_loop
from app.main import app
from app.models.client import Client


def test_stream_cashflow_uses_db_demographics_no_prompt(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]

    client_id = 960000102
    with Session() as db:
        client = db.query(Client).filter(Client.id == client_id).first()
        if client is None:
            client = Client(
                id=client_id,
                id_number_raw=str(client_id),
                id_number=str(client_id),
                full_name="Test User",
                birth_date=date(1954, 1, 1),
                gender="male",
            )
            db.add(client)
            db.commit()

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for deterministic cashflow")

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

    def fake_execute_tool_call(*args, **kwargs) -> str:
        raise AssertionError(
            "No tools should be executed for cashflow without an existing plan"
        )

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    resp = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "תזרים. יעד נטו: 30000"}],
            "pension_portfolio": [],
        },
    )

    assert resp.status_code == 200
    assert resp.text.strip() == "אין תכנית קיימת להצגת תזרים. יש לבנות תכנית תחילה."
