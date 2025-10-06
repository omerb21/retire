"""
Commutation entity model for SQLAlchemy ORM - compatible with rights fixation system
"""
from sqlalchemy import Column, Integer, ForeignKey, Float, Date, DateTime, func
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base

def utcnow():
    return datetime.now(timezone.utc)

class Commutation(Base):
    __tablename__ = "commutation"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pension_id = Column(Integer, ForeignKey("pension.id", ondelete="CASCADE"), nullable=False)
    commutation_date = Column(Date, nullable=True)
    commutation_amount = Column(Float, nullable=True)
    commutation_ratio = Column(Float, nullable=True)  # ׳׳—׳•׳– ׳”׳™׳•׳•׳
    impact_on_exemption = Column(Float, nullable=True)  # ׳₪׳’׳™׳¢׳” ׳‘׳×׳§׳¨׳”

    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow, server_default=func.now())

    pension = relationship("Pension", backref="commutations")
    
    def to_dict(self):
        return {
            "id": self.id,
            "pension_id": self.pension_id,
            "commutation_date": self.commutation_date.isoformat() if self.commutation_date else None,
            "commutation_amount": self.commutation_amount,
            "commutation_ratio": self.commutation_ratio,
            "impact_on_exemption": self.impact_on_exemption
        }

