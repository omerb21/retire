"""Acceptance tests for Agent Eyes trace infrastructure.

Covers:
  1. trace_writer persists events with is_truncated / payload_size
  2. Debug API auth: 404 when disabled, 401 on bad token, 200 on valid token
  3. Debug API returns events in chronological order
  4. Truncation policy marks large payloads correctly
"""

import json
import os
import uuid

import pytest
from fastapi.testclient import TestClient

from tests.conftest import test_client

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_event(db, **kwargs):
    """Insert an AgentTraceEvent row via the writer and return the row."""
    from app.services.agent_trace_logger import log_trace_event

    log_trace_event(**kwargs)


def _count_events(db, trace_id: str) -> int:
    from app.models.agent_trace_event import AgentTraceEvent

    return (
        db.query(AgentTraceEvent).filter(AgentTraceEvent.trace_id == trace_id).count()
    )


def _get_events(db, trace_id: str):
    from app.models.agent_trace_event import AgentTraceEvent

    return (
        db.query(AgentTraceEvent)
        .filter(AgentTraceEvent.trace_id == trace_id)
        .order_by(AgentTraceEvent.created_at.asc(), AgentTraceEvent.id.asc())
        .all()
    )


# ---------------------------------------------------------------------------
# 1. Trace writer unit tests
# ---------------------------------------------------------------------------


class TestTraceWriter:
    """Verify log_trace_event persists rows with correct fields."""

    def test_basic_event_persisted(self, db_session):
        tid = f"test-{uuid.uuid4().hex[:12]}"
        _write_event(
            db_session,
            trace_id=tid,
            event_type="user_input",
            payload={"msg": "hello"},
            client_id=1,
            endpoint="/test",
        )
        events = _get_events(db_session, tid)
        assert len(events) == 1
        row = events[0]
        assert row.event_type == "user_input"
        assert row.is_truncated is False
        assert row.payload_size is not None
        assert row.payload_size > 0

    def test_truncation_on_large_payload(self, db_session):
        tid = f"test-trunc-{uuid.uuid4().hex[:12]}"
        big_payload = {"data": "x" * 600_000}
        _write_event(
            db_session,
            trace_id=tid,
            event_type="llm_request_prepared",
            payload=big_payload,
        )
        events = _get_events(db_session, tid)
        assert len(events) == 1
        row = events[0]
        assert row.is_truncated is True
        assert row.payload_size > 500_000

    def test_multiple_event_types(self, db_session):
        tid = f"test-multi-{uuid.uuid4().hex[:12]}"
        for etype in [
            "user_input",
            "llm_request_prepared",
            "tool_call",
            "tool_result",
            "assistant_output",
        ]:
            _write_event(
                db_session, trace_id=tid, event_type=etype, payload={"t": etype}
            )
        assert _count_events(db_session, tid) == 5


# ---------------------------------------------------------------------------
# 2. Debug API auth tests
# ---------------------------------------------------------------------------


class TestDebugAPIAuth:
    """Verify security gates on /api/v1/debug/traces."""

    def test_404_when_disabled(self, test_client: TestClient):
        os.environ.pop("AGENT_TRACE_DEBUG_ENABLED", None)
        resp = test_client.get("/api/v1/debug/traces")
        assert resp.status_code == 404

    def test_401_without_token(self, test_client: TestClient):
        os.environ["AGENT_TRACE_DEBUG_ENABLED"] = "1"
        os.environ["ADMIN_DEBUG_TOKEN"] = "secret123"
        try:
            resp = test_client.get("/api/v1/debug/traces")
            assert resp.status_code == 401
        finally:
            os.environ.pop("AGENT_TRACE_DEBUG_ENABLED", None)
            os.environ.pop("ADMIN_DEBUG_TOKEN", None)

    def test_401_with_wrong_token(self, test_client: TestClient):
        os.environ["AGENT_TRACE_DEBUG_ENABLED"] = "1"
        os.environ["ADMIN_DEBUG_TOKEN"] = "secret123"
        try:
            resp = test_client.get(
                "/api/v1/debug/traces",
                headers={"X-Admin-Token": "wrong"},
            )
            assert resp.status_code == 401
        finally:
            os.environ.pop("AGENT_TRACE_DEBUG_ENABLED", None)
            os.environ.pop("ADMIN_DEBUG_TOKEN", None)

    def test_200_with_valid_token(self, test_client: TestClient):
        os.environ["AGENT_TRACE_DEBUG_ENABLED"] = "1"
        os.environ["ADMIN_DEBUG_TOKEN"] = "secret123"
        try:
            resp = test_client.get(
                "/api/v1/debug/traces",
                headers={"X-Admin-Token": "secret123"},
            )
            assert resp.status_code == 200
            assert isinstance(resp.json(), list)
        finally:
            os.environ.pop("AGENT_TRACE_DEBUG_ENABLED", None)
            os.environ.pop("ADMIN_DEBUG_TOKEN", None)


# ---------------------------------------------------------------------------
# 3. Debug API returns events chronologically
# ---------------------------------------------------------------------------


class TestDebugAPITraceRetrieval:
    """Verify /api/v1/debug/traces/{trace_id} returns events in order."""

    def test_trace_events_returned_in_order(self, test_client: TestClient, db_session):
        tid = f"test-api-{uuid.uuid4().hex[:12]}"
        event_types = [
            "user_input",
            "llm_request_prepared",
            "tool_call",
            "tool_result",
            "assistant_output",
        ]
        for etype in event_types:
            _write_event(
                db_session, trace_id=tid, event_type=etype, payload={"step": etype}
            )

        os.environ["AGENT_TRACE_DEBUG_ENABLED"] = "1"
        os.environ["ADMIN_DEBUG_TOKEN"] = "secret123"
        try:
            resp = test_client.get(
                f"/api/v1/debug/traces/{tid}",
                headers={"X-Admin-Token": "secret123"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 5
            returned_types = [e["event_type"] for e in data]
            assert returned_types == event_types
            for e in data:
                assert "payload" in e
                assert "is_truncated" in e
                assert "payload_size" in e
        finally:
            os.environ.pop("AGENT_TRACE_DEBUG_ENABLED", None)
            os.environ.pop("ADMIN_DEBUG_TOKEN", None)

    def test_trace_not_found_returns_404(self, test_client: TestClient):
        os.environ["AGENT_TRACE_DEBUG_ENABLED"] = "1"
        os.environ["ADMIN_DEBUG_TOKEN"] = "secret123"
        try:
            resp = test_client.get(
                "/api/v1/debug/traces/nonexistent-trace-id",
                headers={"X-Admin-Token": "secret123"},
            )
            assert resp.status_code == 404
        finally:
            os.environ.pop("AGENT_TRACE_DEBUG_ENABLED", None)
            os.environ.pop("ADMIN_DEBUG_TOKEN", None)

    def test_list_traces_shows_recent(self, test_client: TestClient, db_session):
        tid = f"test-list-{uuid.uuid4().hex[:12]}"
        _write_event(
            db_session, trace_id=tid, event_type="user_input", payload={"x": 1}
        )

        os.environ["AGENT_TRACE_DEBUG_ENABLED"] = "1"
        os.environ["ADMIN_DEBUG_TOKEN"] = "secret123"
        try:
            resp = test_client.get(
                "/api/v1/debug/traces",
                headers={"X-Admin-Token": "secret123"},
            )
            assert resp.status_code == 200
            data = resp.json()
            trace_ids = [t["trace_id"] for t in data]
            assert tid in trace_ids
            matching = [t for t in data if t["trace_id"] == tid][0]
            assert matching["event_count"] >= 1
        finally:
            os.environ.pop("AGENT_TRACE_DEBUG_ENABLED", None)
            os.environ.pop("ADMIN_DEBUG_TOKEN", None)


# ---------------------------------------------------------------------------
# 4. New event types: execution_path, args_normalized, state_source
# ---------------------------------------------------------------------------


class TestNewEventTypes:
    """Verify the new path-tag event types persist correctly."""

    def test_execution_path_event(self, db_session):
        tid = f"test-path-{uuid.uuid4().hex[:12]}"
        _write_event(
            db_session,
            trace_id=tid,
            event_type="execution_path",
            payload={
                "path_id": "chat.stream.deterministic",
                "reason": "deterministic_routing_block_matched",
            },
            client_id=1,
        )
        events = _get_events(db_session, tid)
        assert len(events) == 1
        row = events[0]
        assert row.event_type == "execution_path"
        parsed = json.loads(row.payload_json)
        assert parsed["path_id"] == "chat.stream.deterministic"
        assert "reason" in parsed

    def test_args_normalized_event(self, db_session):
        tid = f"test-norm-{uuid.uuid4().hex[:12]}"
        _write_event(
            db_session,
            trace_id=tid,
            event_type="args_normalized",
            payload={
                "normalizer_name": "normalize_retirement_date_if_jan1_placeholder",
                "before": {"retirement_date": "2030-01-01"},
                "after": {"retirement_date": "2030-06-15"},
            },
            client_id=1,
        )
        events = _get_events(db_session, tid)
        assert len(events) == 1
        row = events[0]
        assert row.event_type == "args_normalized"
        parsed = json.loads(row.payload_json)
        assert (
            parsed["normalizer_name"] == "normalize_retirement_date_if_jan1_placeholder"
        )
        assert parsed["before"]["retirement_date"] != parsed["after"]["retirement_date"]

    def test_state_source_event(self, db_session):
        tid = f"test-state-{uuid.uuid4().hex[:12]}"
        _write_event(
            db_session,
            trace_id=tid,
            event_type="state_source",
            payload={
                "portfolio_source": "db_snapshot",
                "portfolio_count": 5,
                "snapshot_at": "2026-02-10T12:00:00",
                "has_effective_state": True,
            },
            client_id=1,
        )
        events = _get_events(db_session, tid)
        assert len(events) == 1
        row = events[0]
        assert row.event_type == "state_source"
        parsed = json.loads(row.payload_json)
        assert parsed["portfolio_source"] == "db_snapshot"
        assert parsed["portfolio_count"] == 5

    def test_full_chain_with_path_tags(self, db_session):
        """Verify a full chain including the new event types."""
        tid = f"test-full-{uuid.uuid4().hex[:12]}"
        chain = [
            "user_input",
            "execution_path",
            "state_source",
            "llm_request_prepared",
            "tool_call",
            "args_normalized",
            "tool_result",
            "assistant_output",
        ]
        for etype in chain:
            _write_event(
                db_session, trace_id=tid, event_type=etype, payload={"step": etype}
            )
        assert _count_events(db_session, tid) == 8
        events = _get_events(db_session, tid)
        returned_types = [e.event_type for e in events]
        assert returned_types == chain


# ---------------------------------------------------------------------------
# 5. Trace fixtures endpoint
# ---------------------------------------------------------------------------


class TestTraceFixtures:
    """Verify POST /api/v1/debug/trace-fixtures/run."""

    def _headers(self):
        return {"X-Admin-Token": "secret123"}

    def _enable(self):
        os.environ["AGENT_TRACE_DEBUG_ENABLED"] = "1"
        os.environ["ADMIN_DEBUG_TOKEN"] = "secret123"

    def _disable(self):
        os.environ.pop("AGENT_TRACE_DEBUG_ENABLED", None)
        os.environ.pop("ADMIN_DEBUG_TOKEN", None)

    def test_fixture_requires_auth(self, test_client: TestClient):
        os.environ.pop("AGENT_TRACE_DEBUG_ENABLED", None)
        resp = test_client.post(
            "/api/v1/debug/trace-fixtures/run",
            json={"client_id": 1, "fixture": "cashflow"},
        )
        assert resp.status_code == 404

    def test_fixture_invalid_name(self, test_client: TestClient):
        self._enable()
        try:
            resp = test_client.post(
                "/api/v1/debug/trace-fixtures/run",
                json={"client_id": 1, "fixture": "invalid"},
                headers=self._headers(),
            )
            assert resp.status_code == 422
        finally:
            self._disable()

    def test_fixture_missing_client_id(self, test_client: TestClient):
        self._enable()
        try:
            resp = test_client.post(
                "/api/v1/debug/trace-fixtures/run",
                json={"fixture": "cashflow"},
                headers=self._headers(),
            )
            assert resp.status_code == 422
        finally:
            self._disable()

    def test_fixture_cashflow_returns_trace_id(self, test_client: TestClient):
        self._enable()
        try:
            resp = test_client.post(
                "/api/v1/debug/trace-fixtures/run",
                json={"client_id": 1, "fixture": "cashflow"},
                headers=self._headers(),
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "trace_id" in data
            assert data["trace_id"].startswith("fixture-cashflow-")
            assert data["fixture"] == "cashflow"
            assert isinstance(data["notes"], list)
            assert len(data["notes"]) >= 1
        finally:
            self._disable()

    def test_fixture_target_plan_returns_trace_id(self, test_client: TestClient):
        self._enable()
        try:
            resp = test_client.post(
                "/api/v1/debug/trace-fixtures/run",
                json={"client_id": 1, "fixture": "target_plan"},
                headers=self._headers(),
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["trace_id"].startswith("fixture-target_plan-")
            assert data["fixture"] == "target_plan"
        finally:
            self._disable()

    def test_fixture_termination_returns_trace_id(self, test_client: TestClient):
        self._enable()
        try:
            resp = test_client.post(
                "/api/v1/debug/trace-fixtures/run",
                json={"client_id": 1, "fixture": "termination"},
                headers=self._headers(),
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["trace_id"].startswith("fixture-termination-")
            assert data["fixture"] == "termination"
        finally:
            self._disable()

    def test_fixture_trace_has_events_in_db(self, test_client: TestClient, db_session):
        """After running a fixture, the trace_id should have events in the DB."""
        self._enable()
        try:
            resp = test_client.post(
                "/api/v1/debug/trace-fixtures/run",
                json={"client_id": 1, "fixture": "cashflow"},
                headers=self._headers(),
            )
            assert resp.status_code == 200
            trace_id = resp.json()["trace_id"]

            # Verify events exist via the debug API
            resp2 = test_client.get(
                f"/api/v1/debug/traces/{trace_id}",
                headers=self._headers(),
            )
            assert resp2.status_code == 200
            events = resp2.json()
            assert len(events) >= 2  # at least user_input + assistant_output
            event_types = [e["event_type"] for e in events]
            assert "user_input" in event_types
            assert "assistant_output" in event_types
        finally:
            self._disable()
