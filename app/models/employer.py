"""
Employer entity model for SQLAlchemy ORM
"""
from sqlalchemy import Column, Integer, String, DateTime, func
from datetime import datetime, timezone

def utcnow():
    return datetime.now(timezone.utc)

from app.database import Base


class Employer(Base):
    __tablename__ = "employer"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)              # ׳©׳ ׳׳¢׳¡׳™׳§
    reg_no = Column(String(50), nullable=True)              # ׳—.׳₪./׳¢׳•׳¡׳§ - ׳׳ ׳™׳™׳—׳•׳“׳™ ׳‘׳”׳›׳¨׳—
    address_city = Column(String(255), nullable=True)
    address_street = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow, server_default=func.now())

    def __init__(self, *args, **kwargs):
        """Custom constructor tolerant to legacy kwargs.

        Some tests or legacy code may instantiate Employer(name=...). To avoid
        SQLAlchemy raising TypeError for unexpected kwargs in certain mapper
        configurations, we pop "name" before calling the base constructor and
        then assign it explicitly.
        """
        name_value = kwargs.pop("name", None)
        super().__init__(*args, **kwargs)
        if name_value is not None:
            self.name = name_value

