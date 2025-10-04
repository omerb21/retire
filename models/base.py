# models/base.py
# Backwards compatibility: expose Base and useful mixins from a single place.

from app.database import Base  # canonical Base

# Mixins
from datetime import datetime
from sqlalchemy import Column, Integer, DateTime

class IdMixin:
    id = Column(Integer, primary_key=True)

class TimestampMixin:
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

__all__ = ["Base", "IdMixin", "TimestampMixin"]
