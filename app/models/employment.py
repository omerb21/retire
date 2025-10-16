"""
Employment entity model for SQLAlchemy ORM
"""
from sqlalchemy import Column, Integer, ForeignKey, Date, Boolean, Numeric, DateTime, func, Index
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base

def utcnow():
    return datetime.now(timezone.utc)

class Employment(Base):
    __tablename__ = "employment"

    id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(Integer, ForeignKey("client.id", ondelete="CASCADE"), nullable=False)
    employer_id = Column(Integer, ForeignKey("employer.id", ondelete="RESTRICT"), nullable=False)

    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    is_current = Column(Boolean, nullable=False, default=False, server_default="0")

    monthly_salary_nominal = Column(Numeric(12,2), nullable=True)
    # severance_before_termination = Column(Numeric(12,2), nullable=True)  # סכום פיצויים מקורי לפני עזיבה - מושבת עד הרצת migration

    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow, server_default=func.now())

    employer = relationship("Employer", lazy="joined")

# ׳׳™׳ ׳“׳§׳¡׳™׳ ׳©׳™׳׳•׳©׳™׳™׳
Index("ix_employment_client_current", Employment.client_id, Employment.is_current)
Index("ix_employment_employer", Employment.employer_id)

