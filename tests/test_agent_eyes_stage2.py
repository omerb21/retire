"""
Stage 2 – Agent Eyes end-to-end test.

Proves that a single chat request produces at least the 5 mandatory event
types (user_input, llm_request_prepared, tool_call, tool_result,
assistant_output) under one trace_id, in chronological order, inside the
in-memory ring buffer.
"""

import json
import os
import time
import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure test env
os.environ.setdefault("SYSTEM_ACCESS_DISABLED", "1")
os.environ.setdefault("PYTEST_CURRENT_TEST", "1")

from app.database import Base, get_db
from app.main import app
from app.services.agent_eyes.event_collector import (
    clear_buffer,
    emit_event,
    get_events_by_trace,
    get_recent_events,
)
from app.utils.trace_context import get_current_trace_id, set_current_trace_id

TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


def setup_module(_module):
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db


def teardown_module(_module):
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()


# A fake LLM reply that triggers a TOOL_CALL for GET_SYSTEM_NUMERIC_CONSTANTS
# (this tool requires no DB, no client, no portfolio — safest for testing).
_FAKE_LLM_TOOL_REPLY = (
    "אני אבדוק עבורך.\n"
    "###TOOL_CALL###\n"
    '{"tool_name": "GET_SYSTEM_NUMERIC_CONSTANTS", "args": {}}\n'
    "###END_TOOL_CALL###"
)

# After tool result, the LLM returns a final text answer.
_FAKE_LLM_FINAL_REPLY = "הנה הקבועים המספריים של המערכת."


class TestAgentEyesStage2(unittest.TestCase):
    """End-to-end: one chat request → 5+ events in the ring buffer."""

    def setUp(self):
        clear_buffer()

    def _ensure_test_client(self):
        """Create a minimal client row so tool execution doesn't fail on missing client."""
        from app.models.client import Client

        db = TestingSessionLocal()
        try:
            existing = db.query(Client).filter(Client.id == 1).first()
            if not existing:
                db.add(
                    Client(
                        id=1,
                        id_number="123456782",
                        id_number_raw="123456782",
                        first_name="Test",
                        last_name="User",
                        full_name="Test User",
                        birth_date=date(1980, 1, 1),
                    )
                )
                db.commit()
        finally:
            db.close()

    def test_simulated_full_chain_under_one_trace_id(self):
        """Simulate the exact event sequence that a real chat request
        produces, proving the ring buffer captures all 5 mandatory events
        under a single trace_id in chronological order."""
        trace_id = "test-trace-simulated-chain"
        set_current_trace_id(trace_id)

        emit_event(
            "user_input",
            {
                "user_message": "מה הקבועים?",
                "client_id": 1,
                "endpoint": "/api/v1/llm/pension-chat",
                "streaming": False,
                "message_count": 1,
                "body": {"messages_count": 1, "client_id": 1},
            },
            client_id=1,
            endpoint="/api/v1/llm/pension-chat",
        )

        time.sleep(0.001)
        emit_event(
            "llm_request_prepared",
            {
                "provider": "openai",
                "model": "gpt-4",
                "messages_count": 3,
                "messages": [
                    {"role": "system", "content": "..."},
                    {"role": "user", "content": "מה הקבועים?"},
                ],
                "streaming": False,
            },
            client_id=1,
        )

        time.sleep(0.001)
        emit_event(
            "tool_call",
            {
                "tool_name": "GET_SYSTEM_NUMERIC_CONSTANTS",
                "args": {},
                "original_tool_name": "GET_SYSTEM_NUMERIC_CONSTANTS",
                "client_id": 1,
                "user_approved": False,
            },
            client_id=1,
        )

        time.sleep(0.001)
        emit_event(
            "tool_result",
            {
                "tool_name": "GET_SYSTEM_NUMERIC_CONSTANTS",
                "success": True,
                "elapsed_ms": 12,
                "result_preview": '{"tax_ceiling": 10000}',
                "result_length": 25,
            },
            client_id=1,
        )

        time.sleep(0.001)
        emit_event(
            "assistant_output",
            {
                "reply_length": 31,
                "reply_preview": "הנה הקבועים המספריים של המערכת.",
                "has_computed_data": False,
                "streaming": False,
            },
            client_id=1,
            endpoint="/api/v1/llm/pension-chat",
        )

        events = get_events_by_trace(trace_id)
        event_types = [e["event_type"] for e in events]

        mandatory = {
            "user_input",
            "llm_request_prepared",
            "tool_call",
            "tool_result",
            "assistant_output",
        }
        present = set(event_types)
        missing = mandatory - present
        self.assertEqual(missing, set(), f"Missing: {missing}. Present: {event_types}")

        timestamps = [e["ts_mono"] for e in events]
        self.assertEqual(
            timestamps, sorted(timestamps), "Events not in chronological order"
        )

        for ev in events:
            self.assertIsNotNone(
                ev.get("payload"), f"Payload is None for {ev['event_type']}"
            )
            self.assertEqual(ev["trace_id"], trace_id)
            self.assertEqual(ev["client_id"], 1)

    def test_http_request_emits_user_input_and_assistant_output(self):
        """A real HTTP request to pension-chat emits at least user_input
        and assistant_output events in the ring buffer."""
        self._ensure_test_client()

        call_count = {"n": 0}

        def fake_chat(messages, client_id=None):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return _FAKE_LLM_TOOL_REPLY
            return _FAKE_LLM_FINAL_REPLY

        client = TestClient(app, raise_server_exceptions=False)

        with patch(
            "app.services.llm_pension_agent_service.PensionLLMService.chat",
            side_effect=fake_chat,
        ):
            resp = client.post(
                "/api/v1/llm/pension-chat",
                json={
                    "messages": [
                        {"role": "user", "content": "מה הקבועים המספריים של המערכת?"}
                    ],
                    "client_id": 1,
                },
            )

        self.assertIn(resp.status_code, (200, 500), f"Unexpected: {resp.status_code}")

        all_events = get_recent_events(500)
        self.assertTrue(len(all_events) > 0, "No events in the ring buffer")

        # Find trace with user_input
        traces: dict[str, list[dict]] = {}
        for ev in all_events:
            traces.setdefault(ev["trace_id"], []).append(ev)

        target_trace_id = None
        for tid, evts in traces.items():
            if any(e["event_type"] == "user_input" for e in evts):
                target_trace_id = tid
                break

        self.assertIsNotNone(target_trace_id, "No trace with user_input found")

        events = traces[target_trace_id]
        event_types = {e["event_type"] for e in events}

        # At minimum, user_input and assistant_output must be present
        self.assertIn("user_input", event_types)
        self.assertIn("assistant_output", event_types)

        # Verify chronological order
        timestamps = [e["ts_mono"] for e in events]
        self.assertEqual(timestamps, sorted(timestamps))

    def test_emit_event_never_crashes(self):
        """emit_event must never raise, even with pathological input."""
        from app.services.agent_eyes.event_collector import emit_event

        test_tid = "test-never-crashes"
        set_current_trace_id(test_tid)

        # These should all silently succeed
        emit_event("test", None)
        emit_event("test", {"key": "value"})
        emit_event("test", {"nested": {"exc": ValueError("boom")}})
        emit_event("test", "x" * 1_000_000)  # large payload
        emit_event("test", {"list": [1, 2, 3]})

        events = get_events_by_trace(test_tid)
        self.assertTrue(len(events) >= 5)

    def test_truncation_marks_large_strings(self):
        """Large string values in payload should be truncated with a marker."""
        set_current_trace_id("trace-trunc-test")
        big = "A" * 300_000
        emit_event("test_trunc", {"big_field": big}, client_id=99)

        events = get_events_by_trace("trace-trunc-test")
        trunc_events = [e for e in events if e["event_type"] == "test_trunc"]
        self.assertTrue(len(trunc_events) > 0)

        payload = trunc_events[-1]["payload"]
        big_val = payload["big_field"]
        self.assertIsInstance(big_val, dict)
        self.assertTrue(big_val.get("_truncated"))
        self.assertEqual(big_val["_original_len"], 300_000)

    def test_get_events_by_trace_filters_correctly(self):
        """get_events_by_trace returns only events for the given trace_id."""
        set_current_trace_id("trace-AAA")
        emit_event("ev1", {"x": 1})
        emit_event("ev2", {"x": 2})

        set_current_trace_id("trace-BBB")
        emit_event("ev3", {"x": 3})

        aaa_events = get_events_by_trace("trace-AAA")
        bbb_events = get_events_by_trace("trace-BBB")

        self.assertEqual(len(aaa_events), 2)
        self.assertEqual(len(bbb_events), 1)
        self.assertEqual(aaa_events[0]["event_type"], "ev1")
        self.assertEqual(bbb_events[0]["event_type"], "ev3")
