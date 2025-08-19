import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from app.database import get_db, Base
from app.main import app
from app.models import Client

@pytest.fixture(scope="session")
def _test_db(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("db") / "test_suite.db"
    # Set isolation_level to None for SQLite to disable transaction management
    # This will cause each statement to be committed immediately
    engine = create_engine(
        f"sqlite:///{db_path}", 
        connect_args={"check_same_thread": False}, 
        # Force immediate commit and disable cache
        isolation_level=None,
        echo=True  # Enable SQL logging
    )
    # Configure session to be as transparent as possible
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=True,
        expire_on_commit=False,
        bind=engine
    )
    Base.metadata.create_all(bind=engine)
    return {"path": db_path, "engine": engine, "Session": TestingSessionLocal}

@pytest.fixture(scope="session", autouse=True)
def _override_db_dependency(_test_db):
    """
    Override גלובלי ל-get_db: כל קריאות ה-API בטסטים יעבדו מול אותה DB של הטסטים.
    פותר את המצב שבו יוצרים נתונים ישירות ב-Session של הטסטים וה-API "לא רואה" אותם.
    """
    engine = _test_db["engine"]
    
    # Use the same TestingSessionLocal that's used in tests to ensure consistency
    TestingSessionLocal = _test_db["Session"]
    
    def _override_get_db():
        # Important: use the same session factory that's used in tests
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    yield
    # Remove the app.dependency_overrides.clear() to maintain override between tests

@pytest.fixture(autouse=True)
def _enforce_test_db_override(_test_db):
    """
    מבטיח שלפני *כל* טסט, ה־API משתמש באותו engine/SessionMaker של הסוויטה.
    אם טסט אחר ניקה overrides—כאן זה מוחל מחדש.
    """
    Session = _test_db["Session"]

    def _get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db
    yield
    # אל תנקה כאן; השאר את ה־override בתוקף לטסט הבא.

@pytest.fixture()
def db_session(_test_db):
    """Session לשימוש ישיר בטסטים שמבקשים db_session."""
    Session = _test_db["Session"]
    db = Session()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture()
def client():
    """FastAPI TestClient לשימוש בטסטים שמבקשים client."""
    with TestClient(app) as c:
        yield c

@pytest.fixture(scope="session", autouse=True)
def _teardown_db(_test_db):
    yield
    Base.metadata.drop_all(bind=_test_db["engine"])
    _test_db["engine"].dispose()
    try:
        os.remove(_test_db["path"])
    except PermissionError:
        pass
