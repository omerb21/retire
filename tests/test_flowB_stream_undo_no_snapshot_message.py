from datetime import date

from fastapi.testclient import TestClient

from app.main import app
from app.models.client import Client

import app.services.llm_chat.chat_stream_orchestration as stream_orch


def test_flowB_stream_undo_no_snapshot_message(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for undo deterministic flow")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    client_id = 950500002
    with Session() as db:
        client = db.query(Client).filter(Client.id == client_id).first()
        if client is None:
            client = Client(
                id=client_id,
                id_number_raw=str(client_id),
                id_number=str(client_id),
                full_name="Test User",
                birth_date=date(1980, 1, 1),
            )
            db.add(client)
            db.commit()

    api = TestClient(app)
    resp = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "בטל פעולה"}],
        },
    )
    assert resp.status_code == 200
    body = resp.text
    assert "###UI_ACTION###" not in body
    assert "לא נמצא מצב קודם" in body
