"""
Base SQLAlchemy models and common mixins
"""
from app.database import Base
from sqlalchemy import Column, Integer, DateTime
import datetime

class TimestampMixin:
    """Common timestamp fields for all models"""
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

class IdMixin:
    """Common ID field for all models"""
    id = Column(Integer, primary_key=True, autoincrement=True)
