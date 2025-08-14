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
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    return {"path": db_path, "engine": engine, "Session": TestingSessionLocal}

@pytest.fixture(scope="session", autouse=True)
def _override_db_dependency(_test_db):
    """
    Override גלובלי ל-get_db: כל קריאות ה-API בטסטים יעבדו מול אותה DB של הטסטים.
    פותר את המצב שבו יוצרים נתונים ישירות ב-Session של הטסטים וה-API "לא רואה" אותם.
    """
    Session = _test_db["Session"]

    def _override_get_db():
        with Session() as db:
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise

    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.clear()

@pytest.fixture()
def db_session(_test_db):
    """Session לשימוש ישיר בטסטים שמבקשים db_session."""
    Session = _test_db["Session"]
    with Session() as db:
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise

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
