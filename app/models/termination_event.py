"""
TerminationEvent entity model for SQLAlchemy ORM
"""
from sqlalchemy import Column, Integer, ForeignKey, Date, Enum, Numeric, Text, DateTime, func
from sqlalchemy.orm import relationship
import enum
from datetime import datetime, timezone
from app.database import Base

def utcnow():
    return datetime.now(timezone.utc)

class TerminationReason(str, enum.Enum):
    fired = "fired"
    resigned = "resigned"
    retired = "retired"
    deceased = "deceased"
    other = "other"

class TerminationEvent(Base):
    __tablename__ = "termination_event"

    id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(Integer, ForeignKey("client.id", ondelete="CASCADE"), nullable=False)
    employment_id = Column(Integer, ForeignKey("employment.id", ondelete="CASCADE"), nullable=False)

    planned_termination_date = Column(Date, nullable=True)
    actual_termination_date = Column(Date, nullable=True)
    reason = Column(Enum(TerminationReason), nullable=True)

    severance_basis_nominal = Column(Numeric(12,2), nullable=True)  # בסיס פיצויים אם ידוע
    package_paths = Column(Text, nullable=True)  # JSON כטקסט של נתיבי קבצים שנוצרו בשלב B

    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow, server_default=func.now())

    employment = relationship("Employment")
