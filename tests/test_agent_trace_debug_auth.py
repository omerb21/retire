import os
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure test env
os.environ.setdefault("SYSTEM_ACCESS_DISABLED", "1")
os.environ.setdefault("PYTEST_CURRENT_TEST", "1")

from app.database import Base, get_db
from app.models.agent_trace_event import AgentTraceEvent
from app.routers import agent_trace_debug

TEST_DATABASE_URL = "sqlite:///:memory:"
_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestSession = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def _override_get_db():
    db = _TestSession()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


class _ClientHostOverrideMiddleware:
    def __init__(self, app, host: str):
        self.app = app
        self.host = host

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            scope = dict(scope)
            scope["client"] = (self.host, 12345)
        await self.app(scope, receive, send)


def _build_app_with_host(host: str) -> FastAPI:
    app = FastAPI()
    app.dependency_overrides[get_db] = _override_get_db
    app.include_router(agent_trace_debug.router)
    app.add_middleware(_ClientHostOverrideMiddleware, host=host)
    return app


def setup_module(_module):
    Base.metadata.create_all(bind=_engine)


def teardown_module(_module):
    Base.metadata.drop_all(bind=_engine)


def _seed_hebrew_trace(trace_id: str = "trace-hebrew") -> None:
    db = _TestSession()
    try:
        db.query(AgentTraceEvent).delete()
        db.add(
            AgentTraceEvent(
                trace_id=trace_id,
                client_id=1,
                endpoint="/api/v1/debug/test",
                event_type="assistant_output",
                payload_json='{"result_preview": "אני עומד לבצע עכשיו"}',
            )
        )
        db.commit()
    finally:
        db.close()


class TestAgentTraceDebugAuth(unittest.TestCase):
    def setUp(self):
        self._old_enabled = os.environ.get("AGENT_TRACE_DEBUG_ENABLED")
        self._old_token = os.environ.get("ADMIN_DEBUG_TOKEN")
        self._old_env = os.environ.get("APP_ENV")

        os.environ["AGENT_TRACE_DEBUG_ENABLED"] = "1"
        os.environ.pop("ADMIN_DEBUG_TOKEN", None)

    def tearDown(self):
        if self._old_enabled is None:
            os.environ.pop("AGENT_TRACE_DEBUG_ENABLED", None)
        else:
            os.environ["AGENT_TRACE_DEBUG_ENABLED"] = self._old_enabled

        if self._old_token is None:
            os.environ.pop("ADMIN_DEBUG_TOKEN", None)
        else:
            os.environ["ADMIN_DEBUG_TOKEN"] = self._old_token

        if self._old_env is None:
            os.environ.pop("APP_ENV", None)
        else:
            os.environ["APP_ENV"] = self._old_env

    def test_no_token_dev_loopback_allows_200(self):
        os.environ["APP_ENV"] = "development"
        app = _build_app_with_host("127.0.0.1")
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get("/api/v1/debug/traces")
        self.assertEqual(resp.status_code, 200)

    def test_no_token_dev_non_loopback_gets_401(self):
        os.environ["APP_ENV"] = "development"
        app = _build_app_with_host("10.1.2.3")
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get("/api/v1/debug/traces")
        self.assertEqual(resp.status_code, 401)
        self.assertIn("Admin token not configured", resp.text)

    def test_debug_trace_endpoint_has_charset_utf8_and_decodes_hebrew(self):
        os.environ["APP_ENV"] = "development"
        _seed_hebrew_trace("trace-hebrew")

        app = _build_app_with_host("127.0.0.1")
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get("/api/v1/debug/traces/trace-hebrew")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("charset=utf-8", (resp.headers.get("content-type") or "").lower())
        self.assertIn("אני עומד לבצע עכשיו", resp.content.decode("utf-8"))

    def test_no_token_production_loopback_gets_401(self):
        os.environ["APP_ENV"] = "production"
        app = _build_app_with_host("127.0.0.1")
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get("/api/v1/debug/traces")
        self.assertEqual(resp.status_code, 401)
        self.assertIn("Admin token not configured", resp.text)
