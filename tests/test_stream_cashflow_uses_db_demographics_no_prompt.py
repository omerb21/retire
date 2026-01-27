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

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    seen_args: list[dict] = []

    def fake_execute_tool_call(*, tool_name: str, args: dict, client_id: int, db, **kwargs) -> str:
        assert tool_name == "RUN_RETIREMENT_CASHFLOW_ANALYSIS"
        seen_args.append(args)
        assert args.get("gender") == "male"
        assert int(args.get("age")) == 72
        assert args.get("retirement_date") == date.today().isoformat()
        return json.dumps({"success": True}, ensure_ascii=False)

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
    assert seen_args
    assert "כדי לחשב צריך לציין מין וגיל" not in resp.text
