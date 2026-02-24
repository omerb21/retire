import uuid
from typing import Any

from fastapi.testclient import TestClient

from app.main import app


def _is_uuid_str(value: str) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except Exception:
        return False


def test_stage12_golden_non_stream_monthly_summary_traces_correlate(
    monkeypatch,
) -> None:
    import app.services.agent_execution.execute_agent_request as entry_mod
    import app.services.agent_execution.tool_executor as tool_exec_mod
    import app.services.agent_trace_logger as trace_logger_mod

    # Deterministic tool compute
    def fake_compute_monthly_pension_summary(db, client_id: int, today):
        _ = (db, client_id, today)
        return {"pension": "demo"}

    monkeypatch.setattr(
        "app.services.pension_chat_compute.compute_monthly_pension_summary",
        fake_compute_monthly_pension_summary,
    )

    events: list[dict[str, Any]] = []

    def fake_log_trace_event(*, trace_id=None, event_type: str, payload=None, **kwargs):
        _ = kwargs
        events.append(
            {"trace_id": trace_id, "event_type": event_type, "payload": payload}
        )

    monkeypatch.setattr(entry_mod, "log_trace_event", fake_log_trace_event)
    monkeypatch.setattr(tool_exec_mod, "log_trace_event", fake_log_trace_event)
    monkeypatch.setattr(trace_logger_mod, "log_trace_event", fake_log_trace_event)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat",
        json={
            "client_id": 1,
            "messages": [{"role": "user", "content": "monthly_pension"}],
        },
    )

    assert response.status_code == 200

    core_events = [
        e
        for e in events
        if isinstance(e.get("event_type"), str) and e["event_type"].startswith("core_")
    ]
    assert {e.get("trace_id") for e in core_events if e.get("trace_id")}  # at least one

    trace_id = next(e["trace_id"] for e in core_events if e.get("trace_id"))
    assert isinstance(trace_id, str) and _is_uuid_str(trace_id)

    assert {e.get("trace_id") for e in core_events} == {trace_id}

    core_types = {e["event_type"] for e in core_events}
    assert "core_user_input" in core_types
    assert "core_next_action_decided" in core_types
    assert "core_tool_call" in core_types
    assert "core_final_response" in core_types

    tool_call_events = [e for e in events if e.get("event_type") == "tool_call"]
    tool_result_events = [e for e in events if e.get("event_type") == "tool_result"]
    assert tool_call_events
    assert tool_result_events

    tool_call = tool_call_events[-1]
    tool_result = tool_result_events[-1]

    missing_tool_trace_ids = [
        e
        for e in (tool_call_events + tool_result_events)
        if (e.get("trace_id") is None) or (e.get("trace_id") != trace_id)
    ]
    assert not missing_tool_trace_ids, missing_tool_trace_ids

    assert tool_call["payload"].get("tool_name") == "MONTHLY_PENSION_SUMMARY"
    assert tool_result["payload"].get("tool_name") == "MONTHLY_PENSION_SUMMARY"

    tool_call_id = tool_call["payload"].get("tool_call_id")
    assert isinstance(tool_call_id, str) and tool_call_id.strip()
    assert tool_result["payload"].get("tool_call_id") == tool_call_id


def test_stage12_golden_stream_monthly_summary_traces_correlate(monkeypatch) -> None:
    import app.services.agent_execution.execute_agent_request as entry_mod
    import app.services.agent_execution.tool_executor as tool_exec_mod
    import app.services.agent_trace_logger as trace_logger_mod

    # Deterministic tool compute
    def fake_compute_monthly_pension_summary(db, client_id: int, today):
        _ = (db, client_id, today)
        return {"pension": "demo"}

    monkeypatch.setattr(
        "app.services.pension_chat_compute.compute_monthly_pension_summary",
        fake_compute_monthly_pension_summary,
    )

    events: list[dict[str, Any]] = []

    def fake_log_trace_event(*, trace_id=None, event_type: str, payload=None, **kwargs):
        _ = kwargs
        events.append(
            {"trace_id": trace_id, "event_type": event_type, "payload": payload}
        )

    monkeypatch.setattr(entry_mod, "log_trace_event", fake_log_trace_event)
    monkeypatch.setattr(tool_exec_mod, "log_trace_event", fake_log_trace_event)
    monkeypatch.setattr(trace_logger_mod, "log_trace_event", fake_log_trace_event)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [{"role": "user", "content": "monthly_pension"}],
        },
    )

    assert response.status_code == 200
    assert "###COMPUTED_DATA###" in response.text

    core_events = [
        e
        for e in events
        if isinstance(e.get("event_type"), str) and e["event_type"].startswith("core_")
    ]
    trace_id = next(e["trace_id"] for e in core_events if e.get("trace_id"))
    assert isinstance(trace_id, str) and _is_uuid_str(trace_id)

    assert {e.get("trace_id") for e in core_events} == {trace_id}

    tool_call_events = [e for e in events if e.get("event_type") == "tool_call"]
    tool_result_events = [e for e in events if e.get("event_type") == "tool_result"]
    assert tool_call_events
    assert tool_result_events

    tool_call = tool_call_events[-1]
    tool_result = tool_result_events[-1]

    missing_tool_trace_ids = [
        e
        for e in (tool_call_events + tool_result_events)
        if (e.get("trace_id") is None) or (e.get("trace_id") != trace_id)
    ]
    assert not missing_tool_trace_ids, missing_tool_trace_ids

    tool_call_id = tool_call["payload"].get("tool_call_id")
    assert isinstance(tool_call_id, str) and tool_call_id.strip()
    assert tool_result["payload"].get("tool_call_id") == tool_call_id
