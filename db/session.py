"""
Database session management and connection setup
"""

from app.database import Base, SessionLocal, engine
from app.database import get_db as app_get_db


def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Dependency to get database session"""
    yield from app_get_db()
