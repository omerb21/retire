# tests/conftest.py (relevant parts)
import matplotlib
matplotlib.use("Agg")

import pytest
import httpx
import inspect
from app.database import get_engine, Base, SessionLocal
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from app.main import app as fastapi_app

HTTPXClient = getattr(httpx, "Client", None)
if HTTPXClient is not None:
    sig = inspect.signature(HTTPXClient.__init__)
    if "app" not in sig.parameters and hasattr(httpx, "ASGITransport"):
        _orig_init = HTTPXClient.__init__

        def _compat_init(self, *args, app=None, **kwargs):
            if app is not None and "transport" not in kwargs:
                kwargs["transport"] = httpx.ASGITransport(app=app)
            return _orig_init(self, *args, **kwargs)

        HTTPXClient.__init__ = _compat_init

@pytest.fixture(scope="session")
def engine():
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

@pytest.fixture
def client(db_session):
    """Create a test ORM client and attach HTTP methods for API tests.

    This fixture returns a SQLAlchemy Client instance (for tests that need
    direct DB access) but also exposes .get/.post/.put/.delete methods that
    proxy to a FastAPI TestClient, so tests can use it as an HTTP client.
    """
    from app.models.client import Client
    from datetime import date

    # Reuse existing client with this test ID if it already exists, to avoid
    # UNIQUE constraint violations between tests.
    orm_client = db_session.query(Client).filter_by(id_number="123456789").first()
    if orm_client is None:
        # Create ORM client in the shared test database
        orm_client = Client()
        orm_client.id_number = "123456789"
        orm_client.id_number_raw = "123456789"
        orm_client.full_name = "Test User"
        orm_client.first_name = "Test"
        orm_client.last_name = "User"
        orm_client.birth_date = date(1980, 1, 1)
        orm_client.gender = "male"
        orm_client.marital_status = "single"
        orm_client.self_employed = False
        orm_client.current_employer_exists = True
        orm_client.is_active = True

        db_session.add(orm_client)
        db_session.commit()

    # Attach a FastAPI TestClient for HTTP calls
    api_client = TestClient(fastapi_app)

    def _get(url, *args, **kwargs):
        return api_client.get(url, *args, **kwargs)

    def _post(url, *args, **kwargs):
        return api_client.post(url, *args, **kwargs)

    def _put(url, *args, **kwargs):
        return api_client.put(url, *args, **kwargs)

    def _delete(url, *args, **kwargs):
        return api_client.delete(url, *args, **kwargs)

    # Monkey-patch HTTP methods onto the ORM client instance
    orm_client.get = _get
    orm_client.post = _post
    orm_client.put = _put
    orm_client.delete = _delete

    return orm_client

"""Pytest configuration and shared fixtures for tests"""

@pytest.fixture
def test_client():
    """FastAPI TestClient for API tests"""
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)

@pytest.fixture
def test_client_data(client):
    """Test client data dictionary including DB id"""
    from datetime import date
    return {
        "id": client.id,
        "id_number": client.id_number,
        "full_name": client.full_name,
        "first_name": client.first_name,
        "last_name": client.last_name,
        "birth_date": date(1980, 1, 1),
        "gender": client.gender,
        "marital_status": client.marital_status,
        "self_employed": client.self_employed,
        "current_employer_exists": client.current_employer_exists,
        "is_active": client.is_active,
    }


@pytest.fixture(scope="module")
def _test_db():
    """Legacy test database fixture returning a Session factory.

    Some integration tests expect to use it as::

        Session = _test_db["Session"]
        with Session() as db:
            ...

    This fixture now reuses the global SessionLocal used by the FastAPI app,
    and also resets the shared SQLite database to a clean state once per
    module (drop_all/create_all). This ensures deterministic IDs (e.g. the
    first Client created gets id=1) while still sharing the same DB file
    between the API and the tests.
    """
    # Use a temporary session to access the underlying engine
    tmp_session = SessionLocal()
    try:
        engine = tmp_session.get_bind()
        # Reset schema for this module's tests
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
    finally:
        tmp_session.close()

    Session = SessionLocal
    return {"Session": Session}
