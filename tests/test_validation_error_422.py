"""
Tests that RequestValidationError returns 422 with a valid JSON body,
not 500 caused by non-serializable objects (e.g. ValueError in ctx).
"""

import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app

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


client = TestClient(app, raise_server_exceptions=False)


class TestValidationError422(unittest.TestCase):
    """Ensure validation errors return 422 with parseable JSON, never 500."""

    def test_invalid_id_number_returns_422(self):
        """POST /api/v1/clients with an invalid ID number triggers a
        Pydantic ValueError whose ctx contains a raw ValueError object.
        The handler must sanitize it and return 422."""
        resp = client.post(
            "/api/v1/clients",
            json={
                "id_number_raw": "123456789",  # invalid checksum
                "first_name": "Test",
                "last_name": "User",
                "birth_date": "1980-01-01",
            },
        )
        self.assertEqual(
            resp.status_code, 422, f"Expected 422, got {resp.status_code}: {resp.text}"
        )
        body = resp.json()  # must not raise
        self.assertIn("detail", body)
        self.assertIn("path", body)

    def test_missing_required_field_returns_422(self):
        """POST /api/v1/clients without required birth_date -> 422."""
        resp = client.post(
            "/api/v1/clients",
            json={
                "first_name": "Test",
                "last_name": "User",
            },
        )
        self.assertEqual(resp.status_code, 422)
        body = resp.json()
        self.assertIn("detail", body)

    def test_invalid_date_format_returns_422(self):
        """POST /api/v1/clients with malformed birth_date -> 422."""
        resp = client.post(
            "/api/v1/clients",
            json={
                "first_name": "Test",
                "last_name": "User",
                "birth_date": "not-a-date",
            },
        )
        self.assertEqual(resp.status_code, 422)
        body = resp.json()
        self.assertIn("detail", body)

    def test_422_body_is_fully_json_serializable(self):
        """The 422 body must survive a round-trip through json encode/decode
        without any TypeError (no raw Exception objects)."""
        import json

        resp = client.post(
            "/api/v1/clients",
            json={
                "id_number_raw": "111111111",  # invalid checksum
                "birth_date": "1980-01-01",
            },
        )
        self.assertEqual(resp.status_code, 422)
        raw = resp.text
        # Must be valid JSON
        parsed = json.loads(raw)
        # Must round-trip cleanly
        json.dumps(parsed)
