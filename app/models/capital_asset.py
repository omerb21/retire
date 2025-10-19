"""Capital Asset model for investment and capital assets."""

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional

from sqlalchemy import Column, Integer, String, Numeric, Date, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class AssetType(str, Enum):
    """Types of capital assets."""
    RENTAL_PROPERTY = "rental_property"
    INVESTMENT = "investment"
    STOCKS = "stocks"
    BONDS = "bonds"
    MUTUAL_FUNDS = "mutual_funds"
    REAL_ESTATE = "real_estate"
    SAVINGS_ACCOUNT = "savings_account"
    DEPOSITS = "deposits"
    PROVIDENT_FUND = "provident_fund"  # קופת גמל
    EDUCATION_FUND = "education_fund"  # קרן השתלמות
    OTHER = "other"


class PaymentFrequency(str, Enum):
    """Payment frequency options."""
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUALLY = "annually"


class IndexationMethod(str, Enum):
    """Indexation methods for return adjustment."""
    NONE = "none"
    FIXED = "fixed"
    CPI = "cpi"


class TaxTreatment(str, Enum):
    """Tax treatment options."""
    EXEMPT = "exempt"
    TAXABLE = "taxable"
    FIXED_RATE = "fixed_rate"
    CAPITAL_GAINS = "capital_gains"
    TAX_SPREAD = "tax_spread"  # פריסת מס


class CapitalAsset(Base):
    """Capital asset model."""
    
    __tablename__ = "capital_assets"
    
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("client.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Asset details
    asset_name = Column(String(255), nullable=True)  # שם הנכס
    asset_type = Column(String(50), nullable=False)
    description = Column(String(255), nullable=True)
    current_value = Column(Numeric(15, 2), nullable=False)
    monthly_income = Column(Numeric(15, 2), nullable=True)  # תשלום חודשי
    rental_income = Column(Numeric(15, 2), nullable=True)  # הכנסה משכירות (לתאימות לאחור)
    monthly_rental_income = Column(Numeric(15, 2), nullable=True)  # הכנסה חודשית משכירות (לתאימות לאחור)
    annual_return_rate = Column(Numeric(5, 4), nullable=False)
    payment_frequency = Column(String(20), nullable=False)
    
    # Date range
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    
    # Indexation
    indexation_method = Column(String(20), nullable=False, default="none", server_default="none")
    fixed_rate = Column(Numeric(5, 4), nullable=True)  # For fixed indexation
    
    # Tax treatment
    tax_treatment = Column(String(20), nullable=False, default="taxable", server_default="taxable")
    tax_rate = Column(Numeric(5, 4), nullable=True)  # For fixed rate tax
    spread_years = Column(Integer, nullable=True)  # Number of years for tax spread
    
    # Metadata
    remarks = Column(String(500), nullable=True)
    
    # Conversion tracking - מעקב אחר המרה מתיק פנסיוני
    conversion_source = Column(String(1000), nullable=True)  # JSON עם פרטי המקור
    
    # Relationships
    client = relationship("Client", back_populates="capital_assets")
    
    # Constraints
    __table_args__ = (
        CheckConstraint("current_value >= 0", name="check_positive_value"),  # ✅ מאפשר 0 להיוונים
        CheckConstraint("annual_return_rate >= 0", name="check_non_negative_return"),
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
        CheckConstraint("tax_rate IS NULL OR (tax_rate >= 0 AND tax_rate <= 1)", name="check_valid_tax_rate"),
    )
