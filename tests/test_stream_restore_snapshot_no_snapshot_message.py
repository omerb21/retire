from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def test_stream_restore_snapshot_no_snapshot_message(monkeypatch, _test_db) -> None:
    # Guardrail: should be deterministic and not call LLM.
    def fake_chat_stream(messages, client_id=None):
        raise AssertionError(
            "LLM must not be called for deterministic restore snapshot flow"
        )

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

    api = TestClient(app)
    resp = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 940400001,
            "messages": [{"role": "user", "content": "שחזר תיק"}],
        },
    )

    assert resp.status_code == 200
    body = resp.text
    assert "לא נמצא סנאפסוט" in body
    assert "###UI_ACTION###" not in body
