from datetime import date

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app
from app.models.client import Client


def test_stream_general_intro_returns_mapping_no_tools(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]

    client_id = 960000101
    with Session() as db:
        client = db.query(Client).filter(Client.id == client_id).first()
        if client is None:
            db.add(
                Client(
                    id=client_id,
                    id_number_raw=str(client_id),
                    id_number=str(client_id),
                    full_name="Test User",
                    birth_date=date(1954, 1, 1),
                    gender="male",
                )
            )
            db.commit()

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for general intro mapping")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    def fake_execute_tool_call(*args, **kwargs) -> str:
        raise AssertionError("execute_tool_call must not be invoked for general intro mapping")

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    resp = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "אני בן 72. סיימתי לעבוד לפני חודש."}],
            "pension_portfolio": [],
        },
    )

    assert resp.status_code == 200
    body = resp.text
    assert "כותרת: תכנון פרישה – מיפוי ראשוני" in body
    assert "🔧" not in body
    assert "###UI_ACTION###" not in body
