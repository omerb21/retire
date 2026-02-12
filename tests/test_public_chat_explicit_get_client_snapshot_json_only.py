"""
Test: public chat path – explicit GET_CLIENT_SNAPSHOT with JSON-only.

Simulates the production scenario where the user sends a message like
"הפעל GET_CLIENT_SNAPSHOT והחזר רק JSON. בלי הסברים."
through the full stream orchestration pipeline.

Asserts:
  1. The reply is valid parseable JSON.
  2. tool_name == "GET_CLIENT_SNAPSHOT".
  3. Fields ``total_items`` and ``breakdown`` are present.
  4. The LLM is never called (deterministic shortcut).
  5. Agent Eyes trace contains tool_call and tool_result events.
"""

import json

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app
from app.models.client import Client
from app.services.agent_eyes.event_collector import (
    clear_buffer,
    get_events_by_trace,
)


def test_public_chat_explicit_get_client_snapshot_json_only(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]

    # Block LLM — if it's called, the test fails immediately.
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
                id=1,
                id_number_raw="1",
                id_number="1",
                full_name="Test User",
            )
            db.add(client)
            db.commit()

    clear_buffer()

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [
                {
                    "role": "user",
                    "content": "הפעל GET_CLIENT_SNAPSHOT והחזר רק JSON. בלי הסברים.",
                }
            ],
        },
    )

    # ── 1. HTTP 200 ──
    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text[:500]}"
    )

    body = response.text.strip()

    # ── 2. Valid JSON ──
    parsed = json.loads(body)
    assert isinstance(parsed, dict), f"Expected dict, got {type(parsed)}"

    # ── 3. tool_name ──
    assert parsed.get("tool_name") == "GET_CLIENT_SNAPSHOT", (
        f"Expected tool_name='GET_CLIENT_SNAPSHOT', got {parsed.get('tool_name')!r}"
    )

    # ── 4. Required fields ──
    assert "total_items" in parsed, f"Missing 'total_items' in {list(parsed.keys())}"
    assert "breakdown" in parsed, f"Missing 'breakdown' in {list(parsed.keys())}"
    assert parsed.get("success") is True, f"Expected success=True, got {parsed.get('success')}"

    # ── 5. Trace events ──
    trace_id = response.headers.get("X-Trace-Id")
    assert trace_id, "Response must include X-Trace-Id header"

    events = get_events_by_trace(trace_id)
    event_types = [e["event_type"] for e in events]

    assert "tool_call" in event_types, (
        f"Expected 'tool_call' in trace events, got {event_types}"
    )
    assert "tool_result" in event_types, (
        f"Expected 'tool_result' in trace events, got {event_types}"
    )

    # Verify the tool_call event references GET_CLIENT_SNAPSHOT
    tool_call_events = [e for e in events if e["event_type"] == "tool_call"]
    assert any(
        e.get("payload", {}).get("tool_name") == "GET_CLIENT_SNAPSHOT"
        for e in tool_call_events
    ), f"No tool_call event for GET_CLIENT_SNAPSHOT found in {tool_call_events}"

    # Verify execution_path is the shortcut
    exec_path_events = [e for e in events if e["event_type"] == "execution_path"]
    assert any(
        e.get("payload", {}).get("path_id") == "chat.stream.explicit_tool_shortcut"
        for e in exec_path_events
    ), f"Expected explicit_tool_shortcut execution_path, got {exec_path_events}"
