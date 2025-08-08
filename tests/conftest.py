import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app.main import app

# Create in-memory SQLite engine with StaticPool for test isolation
engine = create_engine(
    "sqlite://", 
    connect_args={"check_same_thread": False}, 
    poolclass=StaticPool
)

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

# Create all tables once
Base.metadata.create_all(engine)

# Event listener to restart savepoint after each flush
@event.listens_for(Session, "after_transaction_end")
def restart_savepoint(session, trans):
    if trans.nested and not trans._parent.nested:
        session.begin_nested()

@pytest.fixture(scope="function")
def db_session():
    """Create a database session with transaction rollback for test isolation"""
    connection = engine.connect()
    transaction = connection.begin()
    session = SessionLocal(bind=connection)
    
    # Start a savepoint
    session.begin_nested()
    
    yield session
    
    # Rollback transaction and close connection
    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture(scope="function")
def client(db_session):
    """Create a test client with database dependency override"""
    def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    # Clean up dependency override
    app.dependency_overrides.clear()
