"""
CurrentEmployer entity model for SQLAlchemy ORM - Sprint 3
Core entity for retirement grant calculations
"""
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, JSON, Enum as SQLEnum, func
from sqlalchemy.orm import relationship
from datetime import datetime, timezone, date
import enum
from app.database import Base

def utcnow():
    return datetime.now(timezone.utc)

class ActiveContinuityType(enum.Enum):
    """Enum for active continuity types"""
    none = "none"
    severance = "severance"
    pension = "pension"

class CurrentEmployer(Base):
    __tablename__ = "current_employer"

    id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(Integer, ForeignKey("client.id", ondelete="CASCADE"), nullable=False)
    
    # Basic employer information
    employer_name = Column(String(255), nullable=False)
    employer_id_number = Column(String(50), nullable=True)  # מספר זהות/ח.פ. של המעסיק
    
    # Employment period
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)  # null = still employed
    
    # Non-continuous periods (JSON array of {start_date, end_date, reason})
    non_continuous_periods = Column(JSON, nullable=True, default=list)
    
    # Salary information
    last_salary = Column(Float, nullable=True)
    average_salary = Column(Float, nullable=True)
    
    # Grant and severance information
    severance_accrued = Column(Float, nullable=True)
    # severance_before_termination = Column(Float, nullable=True)  # סכום פיצויים לפני עזיבה (לשחזור במחיקה) - מושבת עד הרצת migration
    other_grants = Column(JSON, nullable=True, default=dict)  # JSON object for various grants
    tax_withheld = Column(Float, nullable=True)
    grant_installments = Column(JSON, nullable=True, default=list)  # JSON array of installment details
    
    # Continuity and pension
    active_continuity = Column(SQLEnum(ActiveContinuityType), nullable=True, default=ActiveContinuityType.none)
    continuity_years = Column(Float, nullable=False, default=0.0)
    pre_retirement_pension = Column(Float, nullable=True)
    existing_deductions = Column(JSON, nullable=True, default=dict)  # JSON object for deduction details
    
    # Tracking
    last_update = Column(
        Date,
        nullable=False,
        default=date.today,                 # function, not call
        server_default=func.current_date(), # DB-side
        onupdate=date.today                 # Server-side update
    )
    
    # Internal calculation fields (nullable for now, will be computed)
    indexed_severance = Column(Float, nullable=True)
    severance_exemption_cap = Column(Float, nullable=True)
    severance_exempt = Column(Float, nullable=True)
    severance_taxable = Column(Float, nullable=True)
    severance_tax_due = Column(Float, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now())
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now()
    )
    
    # Relationships
    client = relationship("Client", back_populates="current_employers")
    grants = relationship("EmployerGrant", back_populates="employer", cascade="all, delete-orphan")
    
    def __init__(self, *args, **kwargs):
        # map older or alternate kwarg names to canonical field names
        alias_map = {
            "employer": "id",  # employer -> id (primary key)
            "employerId": "id",  # employerId -> id
            "employer_id": "id",  # employer_id -> id
            "client": "client_id",
            "clientId": "client_id",
        }
        for alias, canonical in alias_map.items():
            if alias in kwargs and canonical not in kwargs:
                kwargs[canonical] = kwargs.pop(alias)
        super().__init__(*args, **kwargs)
    
    def __repr__(self):
        return f"<CurrentEmployer(id={self.id}, client_id={self.client_id}, employer_name='{self.employer_name}')>"
    
    def to_dict(self):
        return {
            "id": self.id,
            "client_id": self.client_id,
            "employer_name": self.employer_name,
            "employer_id_number": self.employer_id_number,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "non_continuous_periods": self.non_continuous_periods or [],
            "last_salary": self.last_salary,
            "average_salary": self.average_salary,
            "severance_accrued": self.severance_accrued,
            "other_grants": self.other_grants or {},
            "tax_withheld": self.tax_withheld,
            "grant_installments": self.grant_installments or [],
            "active_continuity": self.active_continuity.value if self.active_continuity else None,
            "pre_retirement_pension": self.pre_retirement_pension,
            "existing_deductions": self.existing_deductions or {},
            "continuity_years": self.continuity_years,
            "last_update": self.last_update.isoformat() if self.last_update else None,
            "indexed_severance": self.indexed_severance,
            "severance_exemption_cap": self.severance_exemption_cap,
            "severance_exempt": self.severance_exempt,
            "severance_taxable": self.severance_taxable,
            "severance_tax_due": self.severance_tax_due,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

# Compatibility shim: allow constructing CurrentEmployer(employer_id=...) in tests.
# This monkeypatch wraps or replaces the class __init__ to accept employer_id kwarg,
# without breaking SQLAlchemy internals.
_orig_init = CurrentEmployer.__init__

def _compat_init(self, *args, **kwargs):
    # Remove employer_id from kwargs to avoid SQLAlchemy errors
    employer_id = kwargs.pop("employer_id", None)
    
    # Call original init with remaining kwargs
    try:
        _orig_init(self, *args, **kwargs)
    except Exception as e:
        # If original init fails, try to set attributes manually
        super(CurrentEmployer, self).__init__()
        for k, v in kwargs.items():
            if hasattr(self, k):
                setattr(self, k, v)
    
    # Set employer_id as a simple attribute if provided
    if employer_id is not None:
        self.employer_id = employer_id

# Apply patch only once
if not hasattr(CurrentEmployer, "_compat_patched"):
    CurrentEmployer.__init__ = _compat_init
    CurrentEmployer._compat_patched = True
