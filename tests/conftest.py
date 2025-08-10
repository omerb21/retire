import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import get_db, Base
from app.main import app as fastapi_app

@pytest.fixture(scope="session", autouse=True)
def _test_db(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("db") / "test_suite.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    fastapi_app.dependency_overrides[get_db] = override_get_db

    yield {"engine": engine, "Session": TestingSessionLocal}

    # teardown
    fastapi_app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    try:
        os.remove(db_path)
    except PermissionError:
        pass
