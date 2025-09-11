"""
Unit tests for Client model CRUD operations
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.base import Base
from models.client import Client
from routes.clients import normalize_id

@pytest.fixture
def db_session():
    """Create in-memory SQLite database for testing"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()

def test_client_creation(db_session):
    """Test creating a new client"""
    client = Client(
        id_number_raw="123456789",
        id_number_normalized="123456789",
        full_name="Test User",
        sex="M",
        marital_status="Single"
    )
    
    db_session.add(client)
    db_session.commit()
    db_session.refresh(client)
    
    assert client.id is not None
    assert client.full_name == "Test User"
    assert client.id_number_normalized == "123456789"

def test_client_query_by_normalized_id(db_session):
    """Test querying client by normalized ID"""
    client = Client(
        id_number_raw="000123456789",
        id_number_normalized="123456789",
        full_name="Test User"
    )
    
    db_session.add(client)
    db_session.commit()
    
    found_client = db_session.query(Client).filter(
        Client.id_number_normalized == "123456789"
    ).first()
    
    assert found_client is not None
    assert found_client.full_name == "Test User"
    assert found_client.id_number_raw == "000123456789"

def test_normalize_id_function():
    """Test ID normalization function"""
    assert normalize_id("000123456789") == "123456789"
    assert normalize_id("  123456789  ") == "123456789"
    assert normalize_id("0000000001") == "1"
    assert normalize_id("123456789") == "123456789"

def test_client_unique_constraint(db_session):
    """Test that duplicate raw ID numbers are not allowed"""
    client1 = Client(
        id_number_raw="123456789",
        id_number_normalized="123456789",
        full_name="User One"
    )
    
    client2 = Client(
        id_number_raw="123456789",
        id_number_normalized="123456789",
        full_name="User Two"
    )
    
    db_session.add(client1)
    db_session.commit()
    
    db_session.add(client2)
    
    with pytest.raises(Exception):  # Should raise integrity error
        db_session.commit()
