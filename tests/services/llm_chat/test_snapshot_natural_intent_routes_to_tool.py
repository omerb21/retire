import json

from fastapi.testclient import TestClient

from app.main import app
from app.models.client import Client


def test_snapshot_natural_intent_routes_to_tool_and_computed_data_not_null(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]

    def fake_chat(messages, client_id=None):
        raise AssertionError("LLM must NOT be called for natural snapshot shortcut")

    monkeypatch.setattr(
        "app.services.agent_execution.execute_agent_request.pension_llm_service.chat",
        fake_chat,
        raising=True,
    )

    with Session() as db:
        client = db.query(Client).filter(Client.id == 1).first()
        if client is None:
            client = Client(
                id=1,
                id_number_raw="1",
                id_number="1",
                full_name="Test User",
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
                    "content": "תן לי snapshot קצר של מצב הלקוח.",
                }
            ],
            "executor_only": False,
        },
    )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:500]}"

    body = response.json()
    computed_data = body.get("computed_data")
    assert isinstance(computed_data, dict), f"Expected computed_data dict, got {type(computed_data)}"

    # Ensure we did not fall back to QA.
    assert computed_data.get("tool_name") == "GET_CLIENT_SNAPSHOT"
    assert computed_data.get("success") is True

    breakdown = computed_data.get("breakdown")
    if breakdown is None and isinstance(computed_data.get("snapshot"), dict):
        breakdown = computed_data["snapshot"].get("breakdown")

    assert isinstance(breakdown, dict), "Expected breakdown dict in computed_data.breakdown or computed_data.snapshot.breakdown"


def test_snapshot_natural_intent_missing_client_id_yields_partial_result_v1(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]

    def fake_chat(messages, client_id=None):
        raise AssertionError("LLM must NOT be called for natural snapshot shortcut")

    monkeypatch.setattr(
        "app.services.agent_execution.execute_agent_request.pension_llm_service.chat",
        fake_chat,
        raising=True,
    )

    with Session() as db:
        client = db.query(Client).filter(Client.id == 1).first()
        if client is None:
            client = Client(
                id=1,
                id_number_raw="1",
                id_number="1",
                full_name="Test User",
            )
            db.add(client)
            db.commit()

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat",
        json={
            "messages": [
                {
                    "role": "user",
                    "content": "תן לי snapshot קצר של מצב הלקוח.",
                }
            ],
            "executor_only": False,
        },
    )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:500]}"

    body = response.json()
    computed_data = body.get("computed_data")
    assert isinstance(computed_data, dict), f"Expected computed_data dict, got {type(computed_data)}"

    assert computed_data.get("status") == "missing_data"
    assert computed_data.get("missing_fields") == ["client_id"]
