"""
EmployerGrant entity model for SQLAlchemy ORM - Sprint 3
Grant entity connected to CurrentEmployer for retirement calculations
"""
from sqlalchemy import Column, Integer, Float, Date, DateTime, ForeignKey, Enum as SQLEnum, String, func
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum
from app.database import Base

def utcnow():
    return datetime.now(timezone.utc)

class GrantType(enum.Enum):
    """Enum for grant types"""
    severance = "severance"
    adjustment = "adjustment"
    other = "other"

class EmployerGrant(Base):
    __tablename__ = "employer_grant"

    id = Column(Integer, primary_key=True, autoincrement=True)
    employer_id = Column(Integer, ForeignKey("current_employer.id", ondelete="CASCADE"), nullable=False)
    
    # Grant details
    grant_type = Column(SQLEnum(GrantType), nullable=False)
    grant_amount = Column(Float, nullable=False)
    grant_date = Column(Date, nullable=False)
    
    # Plan details - link to specific pension plan
    plan_name = Column(String, nullable=True)  # שם התכנית מתיק הפנסיה
    plan_start_date = Column(Date, nullable=True)  # תאריך התחלת התכנית (לחישוב מקדם)
    
    # Tax information
    tax_withheld = Column(Float, nullable=True, default=0.0)
    
    # Calculated fields (will be computed by service)
    grant_exempt = Column(Float, nullable=True)
    grant_taxable = Column(Float, nullable=True)
    tax_due = Column(Float, nullable=True)
    indexed_amount = Column(Float, nullable=True)  # Amount after indexing/CPI adjustment
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow, server_default=func.now())
    
    # Relationships
    employer = relationship("CurrentEmployer", back_populates="grants")
    
    def __repr__(self):
        return f"<EmployerGrant(id={self.id}, employer_id={self.employer_id}, grant_type={self.grant_type.value}, amount={self.grant_amount})>"
    
    def to_dict(self):
        return {
            "id": self.id,
            "employer_id": self.employer_id,
            "grant_type": self.grant_type.value if self.grant_type else None,
            "grant_amount": self.grant_amount,
            "grant_date": self.grant_date.isoformat() if self.grant_date else None,
            "plan_name": self.plan_name,
            "plan_start_date": self.plan_start_date.isoformat() if self.plan_start_date else None,
            "tax_withheld": self.tax_withheld,
            "grant_exempt": self.grant_exempt,
            "grant_taxable": self.grant_taxable,
            "tax_due": self.tax_due,
            "indexed_amount": self.indexed_amount,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
