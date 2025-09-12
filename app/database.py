"""
Database configuration module for SQLAlchemy and connection management
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

# Get database URL from environment variable or use default SQLite for development
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./retire.db")

def get_db_url():
    """Get the database URL for external connections"""
    return DATABASE_URL

# Create SQLAlchemy engine
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for declarative models
Base = declarative_base()

def get_engine(url=None):
    """Get SQLAlchemy engine with proper configuration"""
    url = url or DATABASE_URL
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args)

def setup_database(engine):
    """Setup database with proper mapper clearing"""
    from sqlalchemy.orm import clear_mappers
    clear_mappers()
    Base.metadata.create_all(engine)

def get_db():
    """
    Dependency for FastAPI to get database session
    
    Yields:
        SQLAlchemy session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


