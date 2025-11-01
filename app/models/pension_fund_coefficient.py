"""
Pension Fund Coefficient model for SQLAlchemy ORM
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, func, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base

def utcnow():
    return datetime.now(timezone.utc)

class PensionFundCoefficient(Base):
    __tablename__ = "pension_fund_coefficient"

    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Basic parameters
    sex = Column(String(10), nullable=False)  # 'male' or 'female'
    retirement_age = Column(Integer, nullable=False)
    survivors_option = Column(String(50), nullable=False)  # e.g., 'standard', 'spouse', 'none'
    spouse_age_diff = Column(Integer, default=0)  # Age difference from spouse in years
    
    # Coefficient data
    base_coefficient = Column(Float, nullable=False)
    adjust_percent = Column(Float, default=0.0)  # Adjustment percentage if any
    fund_name = Column(String(200), nullable=True)  # Optional: specific fund name
    notes = Column(String(500), nullable=True)  # Any additional notes
    
    # Audit fields
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def to_dict(self):
        return {
            "id": self.id,
            "sex": self.sex,
            "retirement_age": self.retirement_age,
            "survivors_option": self.survivors_option,
            "spouse_age_diff": self.spouse_age_diff,
            "base_coefficient": self.base_coefficient,
            "adjust_percent": self.adjust_percent,
            "fund_name": self.fund_name,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
