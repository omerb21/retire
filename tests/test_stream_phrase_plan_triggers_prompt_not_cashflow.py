from datetime import date

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app
from app.models.client import Client


def test_stream_phrase_plan_triggers_prompt_not_cashflow(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]

    with Session() as db:
        client = db.query(Client).filter(Client.id == 940000001).first()
        if client is None:
            client = Client(
                id=940000001,
                id_number_raw="940000001",
                id_number="940000001",
                full_name="Test User",
                birth_date=date(1980, 1, 1),
            )
            db.add(client)
            db.flush()
        client_id = int(getattr(client, "id", 0) or 0)
        db.commit()

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError(
            "LLM must not be called for deterministic plan-target prompt"
        )

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

    def fake_execute_tool_call(*args, **kwargs) -> str:
        raise AssertionError("No tool must be executed when prompting for target net")

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    resp = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "חשב תכנית קצבה"}],
            "pension_portfolio": [],
        },
    )

    assert resp.status_code == 200
    assert "כתוב: יעד נטו" in resp.text
    assert "RUN_RETIREMENT_CASHFLOW_ANALYSIS" not in resp.text
