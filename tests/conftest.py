import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from app.database import get_db, Base
from app.main import app
from datetime import date

# Simple engine fixture without complex model loading
@pytest.fixture(scope="session")
def engine():
    # Create a fresh engine for each test session
    from sqlalchemy import create_engine
    from app.database import Base
    
    eng = create_engine(
        "sqlite:///:memory:", 
        echo=False,
        connect_args={"check_same_thread": False}
    )
    
    # Import all models to register them with Base
    from app.models.client import Client
    from app.models.current_employer import CurrentEmployer
    from app.models.employer_grant import EmployerGrant
    from app.models.additional_income import AdditionalIncome
    from app.models.capital_asset import CapitalAsset
    from app.models.fixation_result import FixationResult
    from app.models.pension_fund import PensionFund
    from app.models.scenario import Scenario
    
    # Create all tables
    Base.metadata.create_all(eng)
    return eng

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
