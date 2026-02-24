"""
Stage 3 – Agent Eyes DB persistence tests.

Proves that emit_event() dual-writes to both the in-memory ring buffer
AND the agent_trace_event DB table, with correct truncation and
chronological ordering.
"""

import json
import os
import time
import unittest
from datetime import date, datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure test env
os.environ.setdefault("SYSTEM_ACCESS_DISABLED", "1")
os.environ.setdefault("PYTEST_CURRENT_TEST", "1")

from app.database import Base
from app.models.agent_trace_event import AgentTraceEvent
from app.services.agent_eyes import event_collector
from app.services.agent_eyes.event_collector import (
    clear_buffer,
    emit_event,
    get_events_by_trace,
    _MAX_DB_PAYLOAD_BYTES,
)
from app.utils.trace_context import set_current_trace_id

# ---------------------------------------------------------------------------
# Test DB setup (in-memory SQLite, isolated from production)
# ---------------------------------------------------------------------------
TEST_DATABASE_URL = "sqlite:///:memory:"
_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestSession = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def setup_module(_module):
    Base.metadata.create_all(bind=_engine)
    # Redirect emit_event DB writes to the test database
    event_collector._session_factory_override = _TestSession


def teardown_module(_module):
    event_collector._session_factory_override = None
    Base.metadata.drop_all(bind=_engine)


class TestStage3Persistence(unittest.TestCase):
    """Verify dual-write: ring buffer + DB."""

    def setUp(self):
        clear_buffer()
        # Clean DB between tests
        db = _TestSession()
        try:
            db.query(AgentTraceEvent).delete()
            db.commit()
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Test 1: 5 events under one trace_id appear in DB
    # ------------------------------------------------------------------
    def test_five_events_persisted_to_db(self):
        """Emit 5 mandatory event types → query DB → all 5 rows present
        with the same trace_id."""
        trace_id = "stage3-five-events"
        set_current_trace_id(trace_id)

        emit_event(
            "user_input",
            {
                "user_message": "מה הקבועים?",
                "client_id": 1,
            },
            client_id=1,
            endpoint="/api/v1/llm/pension-chat",
        )

        emit_event(
            "llm_request_prepared",
            {
                "provider": "openai",
                "model": "gpt-4",
                "messages_count": 3,
            },
            client_id=1,
        )

        emit_event(
            "tool_call",
            {
                "tool_name": "GET_SYSTEM_NUMERIC_CONSTANTS",
                "args": {},
            },
            client_id=1,
        )

        emit_event(
            "tool_result",
            {
                "tool_name": "GET_SYSTEM_NUMERIC_CONSTANTS",
                "success": True,
                "elapsed_ms": 12,
            },
            client_id=1,
        )

        emit_event(
            "assistant_output",
            {
                "reply_length": 31,
                "reply_preview": "הנה הקבועים.",
                "streaming": False,
            },
            client_id=1,
            endpoint="/api/v1/llm/pension-chat",
        )

        # Query DB
        db = _TestSession()
        try:
            rows = (
                db.query(AgentTraceEvent)
                .filter(AgentTraceEvent.trace_id == trace_id)
                .order_by(AgentTraceEvent.created_at)
                .all()
            )
        finally:
            db.close()

        self.assertEqual(len(rows), 5, f"Expected 5 rows, got {len(rows)}")

        db_types = [r.event_type for r in rows]
        mandatory = {
            "user_input",
            "llm_request_prepared",
            "tool_call",
            "tool_result",
            "assistant_output",
        }
        self.assertEqual(
            mandatory - set(db_types), set(), f"Missing: {mandatory - set(db_types)}"
        )

        # All rows share the same trace_id
        for r in rows:
            self.assertEqual(r.trace_id, trace_id)

        # Verify ring buffer also has them
        mem_events = get_events_by_trace(trace_id)
        self.assertEqual(len(mem_events), 5)

    # ------------------------------------------------------------------
    # Test 2: DB rows are in chronological order
    # ------------------------------------------------------------------
    def test_db_events_chronological_order(self):
        """Events written to DB must come back in created_at order."""
        trace_id = "stage3-chrono"
        set_current_trace_id(trace_id)

        for i in range(5):
            emit_event(f"step_{i}", {"seq": i}, client_id=1)
            time.sleep(0.002)  # ensure distinct timestamps

        db = _TestSession()
        try:
            rows = (
                db.query(AgentTraceEvent)
                .filter(AgentTraceEvent.trace_id == trace_id)
                .order_by(AgentTraceEvent.created_at)
                .all()
            )
        finally:
            db.close()

        self.assertEqual(len(rows), 5)

        timestamps = [r.created_at for r in rows]
        self.assertEqual(
            timestamps, sorted(timestamps), "DB rows are not in chronological order"
        )

        # Verify event_type order matches emission order
        types = [r.event_type for r in rows]
        self.assertEqual(types, [f"step_{i}" for i in range(5)])

    # ------------------------------------------------------------------
    # Test 3: Large payload is truncated in DB with _truncated marker
    # ------------------------------------------------------------------
    def test_large_payload_truncated_in_db(self):
        """A payload exceeding _MAX_DB_PAYLOAD_BYTES is stored truncated
        with _truncated=true and _original_len in the JSON."""
        trace_id = "stage3-trunc"
        set_current_trace_id(trace_id)

        # Create a payload whose JSON serialization exceeds 128 KB
        big_value = "X" * (_MAX_DB_PAYLOAD_BYTES + 50_000)
        emit_event("big_event", {"big_field": big_value}, client_id=1)

        db = _TestSession()
        try:
            row = (
                db.query(AgentTraceEvent)
                .filter(AgentTraceEvent.trace_id == trace_id)
                .first()
            )
        finally:
            db.close()

        self.assertIsNotNone(row)
        self.assertTrue(row.is_truncated, "is_truncated should be True")
        self.assertIsNotNone(row.payload_size)
        self.assertGreater(row.payload_size, _MAX_DB_PAYLOAD_BYTES)

        # The stored JSON should contain the _truncated marker
        stored = json.loads(row.payload_json)
        self.assertTrue(stored.get("_truncated"))
        self.assertIn("_original_len", stored)

    # ------------------------------------------------------------------
    # Test 4: Small payload stored intact (not truncated)
    # ------------------------------------------------------------------
    def test_small_payload_stored_intact(self):
        """A normal-sized payload is stored as-is without truncation."""
        trace_id = "stage3-small"
        set_current_trace_id(trace_id)

        emit_event("small_event", {"key": "value", "num": 42}, client_id=1)

        db = _TestSession()
        try:
            row = (
                db.query(AgentTraceEvent)
                .filter(AgentTraceEvent.trace_id == trace_id)
                .first()
            )
        finally:
            db.close()

        self.assertIsNotNone(row)
        self.assertFalse(row.is_truncated)

        stored = json.loads(row.payload_json)
        self.assertEqual(stored["key"], "value")
        self.assertEqual(stored["num"], 42)

    # ------------------------------------------------------------------
    # Test 5: emit_event never crashes even if DB is broken
    # ------------------------------------------------------------------
    def test_emit_never_raises_on_db_failure(self):
        """If the DB session factory raises, emit_event still succeeds
        (ring buffer write) without propagating the exception."""
        trace_id = "stage3-db-fail"
        set_current_trace_id(trace_id)

        def broken_session_factory():
            raise RuntimeError("DB is down")

        original = event_collector._session_factory_override
        try:
            event_collector._session_factory_override = broken_session_factory
            # This must NOT raise
            emit_event("resilient_event", {"ok": True}, client_id=1)
        finally:
            event_collector._session_factory_override = original

        # Ring buffer should still have the event
        mem_events = get_events_by_trace(trace_id)
        self.assertEqual(len(mem_events), 1)
        self.assertEqual(mem_events[0]["event_type"], "resilient_event")

    # ------------------------------------------------------------------
    # Test 6: client_id and endpoint stored correctly
    # ------------------------------------------------------------------
    def test_client_id_and_endpoint_stored(self):
        """client_id and endpoint are persisted to the DB row."""
        trace_id = "stage3-fields"
        set_current_trace_id(trace_id)

        emit_event(
            "field_test", {"x": 1}, client_id=42, endpoint="/api/v1/llm/pension-chat"
        )

        db = _TestSession()
        try:
            row = (
                db.query(AgentTraceEvent)
                .filter(AgentTraceEvent.trace_id == trace_id)
                .first()
            )
        finally:
            db.close()

        self.assertIsNotNone(row)
        self.assertEqual(row.client_id, 42)
        self.assertEqual(row.endpoint, "/api/v1/llm/pension-chat")
        self.assertEqual(row.event_type, "field_test")
