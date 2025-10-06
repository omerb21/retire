# tests/conftest.py (relevant parts)
import matplotlib
matplotlib.use("Agg")

import pytest
from app.database import get_engine, Base, SessionLocal
from sqlalchemy.orm import clear_mappers

def import_models():
    # import all model modules here (only after clear_mappers)
    import app.models.client
    import app.models.current_employer
    # ... כל שאר המודלים ...

@pytest.fixture(scope="session")
def engine():
    engine = get_engine()
    # Reset mappers before import
    clear_mappers()
    import_models()
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def db_session(engine):
    connection = engine.connect()
    tx = connection.begin()
    session = SessionLocal(bind=connection)
    try:
        yield session
    finally:
        session.close()
        tx.rollback()
        connection.close()
        transaction.rollback()
        connection.close()

@pytest.fixture
def client(db_session):
    """Create test client"""
    from app.models.client import Client
    from datetime import date
    
    client = Client()
    client.id_number = "123456789"
    client.id_number_raw = "123456789"
    client.full_name = "Test User"
    client.first_name = "Test"
    client.last_name = "User"
    client.birth_date = date(1980, 1, 1)
    client.gender = "male"
    client.marital_status = "single"
    client.self_employed = False
    client.current_employer_exists = True
    client.is_active = True
    
    db_session.add(client)
    db_session.commit()
    return client

# Legacy fixture for backward compatibility
@pytest.fixture
def _test_db(db_session):
    """Legacy test database fixture"""
    return db_session

@pytest.fixture
def test_client(client):
    """Alias for client fixture"""
    return client

@pytest.fixture
def test_client_data():
    """Test client data dictionary"""
    from datetime import date
    return {
        "id_number": "123456789",
        "full_name": "Test User",
        "first_name": "Test",
        "last_name": "User",
        "birth_date": date(1980, 1, 1),
        "gender": "male",
        "marital_status": "single",
        "self_employed": False,
        "current_employer_exists": True,
        "is_active": True
    }
