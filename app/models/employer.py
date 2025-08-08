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

