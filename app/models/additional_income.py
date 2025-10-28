"""Additional Income model for non-pension income sources."""

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional

from sqlalchemy import Column, Integer, String, Numeric, Date, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class IncomeSourceType(str, Enum):
    """Types of additional income sources."""
    RENTAL = "rental"
    DIVIDENDS = "dividends"
    INTEREST = "interest"
    BUSINESS = "business"
    SALARY = "salary"
    OTHER = "other"

# Add aliases for lowercase access to prevent AttributeError
IncomeSourceType.rental = IncomeSourceType.RENTAL
IncomeSourceType.dividends = IncomeSourceType.DIVIDENDS
IncomeSourceType.interest = IncomeSourceType.INTEREST
IncomeSourceType.business = IncomeSourceType.BUSINESS
IncomeSourceType.salary = IncomeSourceType.SALARY
IncomeSourceType.other = IncomeSourceType.OTHER


class PaymentFrequency(str, Enum):
    """Payment frequency options."""
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUALLY = "annually"


class IndexationMethod(str, Enum):
    """Indexation methods for income adjustment."""
    NONE = "none"
    FIXED = "fixed"
    CPI = "cpi"


class TaxTreatment(str, Enum):
    """Tax treatment options."""
    EXEMPT = "exempt"
    TAXABLE = "taxable"
    FIXED_RATE = "fixed_rate"


class AdditionalIncome(Base):
    """Additional income source model."""
    
    __tablename__ = "additional_income"
    
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("client.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Income details
    source_type = Column(String(50), nullable=False)
    description = Column(String(255), nullable=True)
    amount = Column(Numeric(12, 2), nullable=False)
    frequency = Column(String(20), nullable=False)
    
    # Date range
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    
    # Indexation
    indexation_method = Column(String(20), nullable=False, default="none", server_default="none")
    fixed_rate = Column(Numeric(5, 4), nullable=True)  # For fixed indexation
    
    # Tax treatment
    tax_treatment = Column(String(20), nullable=False, default="taxable", server_default="taxable")
    tax_rate = Column(Numeric(5, 2), nullable=True)  # For fixed rate tax (0-99%)
    
    # Metadata
    remarks = Column(String(500), nullable=True)
    
    # Relationships
    client = relationship("Client", back_populates="additional_incomes")
    
    # Constraints
    __table_args__ = (
        CheckConstraint("amount > 0", name="check_positive_amount"),
        CheckConstraint("end_date IS NULL OR end_date >= start_date", name="check_valid_date_range"),
        CheckConstraint(
            "indexation_method != 'fixed' OR fixed_rate IS NOT NULL",
            name="check_fixed_rate_when_fixed_indexation"
        ),
        CheckConstraint(
            "tax_treatment != 'fixed_rate' OR tax_rate IS NOT NULL",
            name="check_tax_rate_when_fixed_tax"
        ),
        CheckConstraint("fixed_rate IS NULL OR fixed_rate >= 0", name="check_non_negative_fixed_rate"),
        CheckConstraint("tax_rate IS NULL OR (tax_rate >= 0 AND tax_rate <= 99)", name="check_valid_tax_rate"),
    )
