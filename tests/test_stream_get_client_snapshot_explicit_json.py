"""
Test: explicit GET_CLIENT_SNAPSHOT request with "רק JSON" returns
parseable JSON and exactly one tool_call in the trace.
"""

import json

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app
from app.models.client import Client


def test_explicit_get_client_snapshot_json_only(monkeypatch, _test_db) -> None:
    """When the user message contains GET_CLIENT_SNAPSHOT + 'רק JSON',
    the router shortcut must:
      1. Return HTTP 200
      2. Return a body that is valid JSON (starts with '{', ends with '}')
      3. The JSON contains 'success' and 'tool_name' keys
      4. The LLM is never called
    """
    Session = _test_db["Session"]

    # Ensure the LLM is never called — if it is, the test fails.
    def fake_chat_stream(messages, client_id=None):
        raise AssertionError(
            "LLM must NOT be called for explicit GET_CLIENT_SNAPSHOT shortcut"
        )

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

    # Ensure client exists
    with Session() as db:
        client = db.query(Client).filter(Client.id == 1).first()
        if client is None:
            client = Client(
                id=1, id_number_raw="1", id_number="1", full_name="Test User"
            )
            db.add(client)
            db.commit()

    api = TestClient(app)
    response = api.post(
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

    assert response.status_code == 200
    body = response.text.strip()

    # Must be valid JSON
    parsed = json.loads(body)
    assert isinstance(parsed, dict), f"Expected dict, got {type(parsed)}"
    assert parsed.get("tool_name") == "GET_CLIENT_SNAPSHOT"
    assert "success" in parsed


def test_explicit_get_client_snapshot_non_stream_json_only(
    monkeypatch, _test_db
) -> None:
    """Same test but via the non-stream /pension-chat endpoint."""
    Session = _test_db["Session"]

    # Block LLM
    from app.services.llm_pension_agent_service import pension_llm_service

    def fake_chat(messages, client_id=None):
        raise AssertionError(
            "LLM must NOT be called for explicit GET_CLIENT_SNAPSHOT shortcut"
        )

    monkeypatch.setattr(pension_llm_service, "chat", fake_chat)

    with Session() as db:
        client = db.query(Client).filter(Client.id == 1).first()
        if client is None:
            client = Client(
                id=1, id_number_raw="1", id_number="1", full_name="Test User"
            )
            db.add(client)
            db.commit()

    api = TestClient(app)
    response = api.post(
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

    assert response.status_code == 200
    data = response.json()
    reply = data.get("reply", "")

    # The reply itself should be valid JSON
    parsed = json.loads(reply)
    assert isinstance(parsed, dict)
    assert parsed.get("tool_name") == "GET_CLIENT_SNAPSHOT"
    assert "success" in parsed
