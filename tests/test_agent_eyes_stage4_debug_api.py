"""
Stage 4 – Agent Eyes Debug API tests.

Verifies:
  - 404 when AGENT_EYES_DEBUG_API_ENABLED is off
  - 403 when token is missing or wrong
  - GET /traces returns grouped trace list
  - GET /traces/{trace_id} returns chronological events
  - DELETE /traces/{trace_id} removes rows
"""

import json
import os
import time
import unittest
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure test env
os.environ.setdefault("SYSTEM_ACCESS_DISABLED", "1")
os.environ.setdefault("PYTEST_CURRENT_TEST", "1")

from app.database import Base, get_db
from app.main import app
from app.models.agent_trace_event import AgentTraceEvent
from app.services.agent_eyes import event_collector
from app.services.agent_eyes.event_collector import clear_buffer, emit_event
from app.utils.trace_context import set_current_trace_id

# ---------------------------------------------------------------------------
# Test DB (in-memory SQLite)
# ---------------------------------------------------------------------------
TEST_DATABASE_URL = "sqlite:///:memory:"
_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestSession = sessionmaker(autocommit=False, autoflush=False, bind=_engine)

_ADMIN_TOKEN = "test-secret-token-stage4"
_BASE = "/api/v1/agent-eyes"


def _override_get_db():
    db = _TestSession()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


def setup_module(_module):
    Base.metadata.create_all(bind=_engine)
    app.dependency_overrides[get_db] = _override_get_db
    event_collector._session_factory_override = _TestSession


def teardown_module(_module):
    event_collector._session_factory_override = None
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=_engine)


def _clean_db():
    db = _TestSession()
    try:
        db.query(AgentTraceEvent).delete()
        db.commit()
    finally:
        db.close()


def _seed_events():
    """Seed two traces with known data for query tests."""
    clear_buffer()
    _clean_db()

    set_current_trace_id("trace-AAA")
    emit_event(
        "user_input", {"msg": "hello"}, client_id=1, endpoint="/api/v1/llm/pension-chat"
    )
    time.sleep(0.002)
    emit_event(
        "assistant_output",
        {"reply": "world"},
        client_id=1,
        endpoint="/api/v1/llm/pension-chat",
    )

    time.sleep(0.002)
    set_current_trace_id("trace-BBB")
    emit_event(
        "user_input",
        {"msg": "second"},
        client_id=2,
        endpoint="/api/v1/llm/pension-chat-stream",
    )
    time.sleep(0.002)
    emit_event("tool_call", {"tool": "X"}, client_id=2)
    time.sleep(0.002)
    emit_event("tool_result", {"ok": True}, client_id=2)


# ===================================================================
# Auth / feature-flag tests
# ===================================================================


class TestDebugAPIAuth(unittest.TestCase):

    def test_disabled_returns_404(self):
        """When AGENT_EYES_DEBUG_API_ENABLED is not '1', all endpoints return 404."""
        old_enabled = os.environ.pop("AGENT_EYES_DEBUG_API_ENABLED", None)
        old_token = os.environ.pop("AGENT_EYES_ADMIN_TOKEN", None)
        try:
            client = TestClient(app, raise_server_exceptions=False)
            for path in ["/traces", "/traces/some-id"]:
                resp = client.get(f"{_BASE}{path}")
                self.assertEqual(resp.status_code, 404, f"Expected 404 for {path}")
        finally:
            if old_enabled is not None:
                os.environ["AGENT_EYES_DEBUG_API_ENABLED"] = old_enabled
            if old_token is not None:
                os.environ["AGENT_EYES_ADMIN_TOKEN"] = old_token

    def test_enabled_but_no_token_configured_returns_404(self):
        """If enabled but AGENT_EYES_ADMIN_TOKEN is empty, return 404 (don't open unauthenticated)."""
        os.environ["AGENT_EYES_DEBUG_API_ENABLED"] = "1"
        old_token = os.environ.pop("AGENT_EYES_ADMIN_TOKEN", None)
        try:
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get(f"{_BASE}/traces")
            self.assertEqual(resp.status_code, 404)
        finally:
            if old_token is not None:
                os.environ["AGENT_EYES_ADMIN_TOKEN"] = old_token

    def test_missing_token_header_returns_403(self):
        """Enabled + token configured, but request has no header → 403."""
        os.environ["AGENT_EYES_DEBUG_API_ENABLED"] = "1"
        os.environ["AGENT_EYES_ADMIN_TOKEN"] = _ADMIN_TOKEN
        try:
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get(f"{_BASE}/traces")
            self.assertEqual(resp.status_code, 403)
        finally:
            pass

    def test_wrong_token_returns_403(self):
        """Enabled + token configured, but wrong token → 403."""
        os.environ["AGENT_EYES_DEBUG_API_ENABLED"] = "1"
        os.environ["AGENT_EYES_ADMIN_TOKEN"] = _ADMIN_TOKEN
        try:
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get(
                f"{_BASE}/traces",
                headers={"X-Admin-Token": "wrong-token"},
            )
            self.assertEqual(resp.status_code, 403)
        finally:
            pass

    def test_correct_token_returns_200(self):
        """Enabled + correct token → 200."""
        os.environ["AGENT_EYES_DEBUG_API_ENABLED"] = "1"
        os.environ["AGENT_EYES_ADMIN_TOKEN"] = _ADMIN_TOKEN
        try:
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get(
                f"{_BASE}/traces",
                headers={"X-Admin-Token": _ADMIN_TOKEN},
            )
            self.assertEqual(resp.status_code, 200)
        finally:
            pass


# ===================================================================
# Functional tests (all with auth enabled)
# ===================================================================


class TestDebugAPIEndpoints(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.environ["AGENT_EYES_DEBUG_API_ENABLED"] = "1"
        os.environ["AGENT_EYES_ADMIN_TOKEN"] = _ADMIN_TOKEN

    def setUp(self):
        _seed_events()
        self.client = TestClient(app, raise_server_exceptions=False)
        self.headers = {"X-Admin-Token": _ADMIN_TOKEN}

    # ------------------------------------------------------------------
    # GET /traces
    # ------------------------------------------------------------------
    def test_list_traces_returns_items(self):
        """List traces returns both trace-AAA and trace-BBB."""
        resp = self.client.get(f"{_BASE}/traces", headers=self.headers)
        self.assertEqual(resp.status_code, 200)

        body = resp.json()
        self.assertIn("items", body)
        items = body["items"]
        trace_ids = {item["trace_id"] for item in items}
        self.assertIn("trace-AAA", trace_ids)
        self.assertIn("trace-BBB", trace_ids)

    def test_list_traces_ordered_by_last_event_desc(self):
        """trace-BBB was seeded after trace-AAA, so it should appear first."""
        resp = self.client.get(f"{_BASE}/traces", headers=self.headers)
        items = resp.json()["items"]
        trace_ids = [item["trace_id"] for item in items]

        idx_a = trace_ids.index("trace-AAA")
        idx_b = trace_ids.index("trace-BBB")
        self.assertLess(idx_b, idx_a, "trace-BBB should appear before trace-AAA")

    def test_list_traces_events_count(self):
        """trace-AAA has 2 events, trace-BBB has 3."""
        resp = self.client.get(f"{_BASE}/traces", headers=self.headers)
        items = {item["trace_id"]: item for item in resp.json()["items"]}

        self.assertEqual(items["trace-AAA"]["events_count"], 2)
        self.assertEqual(items["trace-BBB"]["events_count"], 3)

    def test_list_traces_filter_by_client_id(self):
        """Filter by client_id=2 returns only trace-BBB."""
        resp = self.client.get(
            f"{_BASE}/traces?client_id=2",
            headers=self.headers,
        )
        items = resp.json()["items"]
        trace_ids = {item["trace_id"] for item in items}
        self.assertIn("trace-BBB", trace_ids)
        self.assertNotIn("trace-AAA", trace_ids)

    # ------------------------------------------------------------------
    # GET /traces/{trace_id}
    # ------------------------------------------------------------------
    def test_get_trace_returns_chronological_events(self):
        """Events for trace-BBB are returned in created_at ASC order."""
        resp = self.client.get(
            f"{_BASE}/traces/trace-BBB",
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 200)

        body = resp.json()
        self.assertEqual(body["trace_id"], "trace-BBB")

        items = body["items"]
        self.assertEqual(len(items), 3)

        # Chronological order
        types = [item["event_type"] for item in items]
        self.assertEqual(types, ["user_input", "tool_call", "tool_result"])

        timestamps = [item["created_at"] for item in items]
        self.assertEqual(timestamps, sorted(timestamps))

    def test_get_trace_not_found(self):
        """Non-existent trace_id returns 404."""
        resp = self.client.get(
            f"{_BASE}/traces/nonexistent",
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 404)

    def test_get_trace_payload_parsed(self):
        """payload_json is returned as parsed JSON, not a raw string."""
        resp = self.client.get(
            f"{_BASE}/traces/trace-AAA",
            headers=self.headers,
        )
        items = resp.json()["items"]
        first = items[0]
        self.assertIsInstance(first["payload_json"], dict)
        self.assertEqual(first["payload_json"]["msg"], "hello")

    # ------------------------------------------------------------------
    # DELETE /traces/{trace_id}
    # ------------------------------------------------------------------
    def test_delete_trace_removes_rows(self):
        """DELETE removes all rows for the trace and returns count."""
        resp = self.client.delete(
            f"{_BASE}/traces/trace-AAA",
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["deleted"], 2)

        # Verify gone
        resp2 = self.client.get(
            f"{_BASE}/traces/trace-AAA",
            headers=self.headers,
        )
        self.assertEqual(resp2.status_code, 404)

    def test_delete_nonexistent_trace_returns_zero(self):
        """DELETE on non-existent trace returns deleted=0."""
        resp = self.client.delete(
            f"{_BASE}/traces/nonexistent",
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["deleted"], 0)
