import json

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app
from app.models.client import Client


def test_stage6_parity_explicit_snapshot_stream_vs_non_stream(monkeypatch, _test_db) -> None:
    """Deterministic parity guard for Stage 6 refactor.

    For explicit GET_CLIENT_SNAPSHOT + 'רק JSON' requests, both stream and
    non-stream endpoints must:

    - not call the LLM
    - return valid JSON
    - return identical JSON payloads

    This ensures the refactor didn't introduce behavioral drift.
    """

    Session = _test_db["Session"]

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must NOT be called for explicit GET_CLIENT_SNAPSHOT shortcut")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    from app.services.llm_pension_agent_service import pension_llm_service

    def fake_chat(messages, client_id=None):
        raise AssertionError("LLM must NOT be called for explicit GET_CLIENT_SNAPSHOT shortcut")

    monkeypatch.setattr(pension_llm_service, "chat", fake_chat)

    with Session() as db:
        client = db.query(Client).filter(Client.id == 1).first()
        if client is None:
            client = Client(id=1, id_number_raw="1", id_number="1", full_name="Test User")
            db.add(client)
            db.commit()

    api = TestClient(app)

    stream_resp = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [
                {
                    "role": "user",
                    "content": "הרץ GET_CLIENT_SNAPSHOT רק JSON בלי הסברים",
                }
            ],
        },
    )
    assert stream_resp.status_code == 200
    stream_payload = json.loads(stream_resp.text.strip())

    non_stream_resp = api.post(
        "/api/v1/llm/pension-chat",
        json={
            "client_id": 1,
            "messages": [
                {
                    "role": "user",
                    "content": "הרץ GET_CLIENT_SNAPSHOT רק JSON",
                }
            ],
        },
    )
    assert non_stream_resp.status_code == 200
    non_stream_reply = non_stream_resp.json().get("reply", "")
    non_stream_payload = json.loads(non_stream_reply)

    assert stream_payload == non_stream_payload
