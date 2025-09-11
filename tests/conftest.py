import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from app.database import get_db, Base
from app.main import app
from app.models.client import Client
from datetime import date

# Engine ברירת מחדל לזיכרון - כל מבחן מקבל טרנזקציה נפרדת
@pytest.fixture(scope="session")
def engine():
    eng = create_engine("sqlite:///:memory:", echo=False)
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
    c = Client(
        first_name="Test",
        last_name="Client",
        birth_date=date(1970, 1, 1),
        id_number="000000000"
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
