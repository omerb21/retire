import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from app.database import get_db, Base
from app.main import app
from datetime import date

# Simple engine fixture - use a file-based SQLite for better stability
@pytest.fixture(scope="session")
def engine():
    import tempfile
    import os
    from sqlalchemy import create_engine
    from app.database import Base
    
    # Create a temporary file for SQLite
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(db_fd)
    
    eng = create_engine(
        f"sqlite:///{db_path}", 
        echo=False,
        connect_args={"check_same_thread": False}
    )
    
    # Use the new setup_database function
    from app.database import setup_database
    setup_database(eng)
    
    yield eng
    
    # Cleanup
    eng.dispose()
    try:
        os.unlink(db_path)
    except:
        pass

@pytest.fixture(scope="function")
def db_session(engine):
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()

# Alias ל־fixture בשם client כדי לשמור על backward compatibility
@pytest.fixture(scope="function")
def client(db_session):
    from app.models.client import Client
    c = Client(
        first_name="Test",
        last_name="Client",
        birth_date=date(1970, 1, 1),
        id_number="000000000",
        is_active=True
    )
    db_session.add(c)
    db_session.flush()  # כדי לקבל id
    return c

# ממשהו שהבדיקות דרשו - test_client נקרא כ־alias ל־client
@pytest.fixture(scope="function")
def test_client(client):
    return client

# fixture שמחזירה data dict עבור שמירת client id וכו'
@pytest.fixture(scope="function")
def test_client_data(test_client):
    return {"client_id": test_client.id, "client_personal_number": test_client.id_number}

# Legacy compatibility fixture for _test_db
@pytest.fixture(scope="session")
def _test_db(engine):
    """Legacy compatibility fixture for existing tests that expect _test_db"""
    TestingSessionLocal = sessionmaker(bind=engine)
    return {
        "engine": engine,
        "Session": TestingSessionLocal,
        "path": ":memory:"  # For compatibility with tests that check path
    }
