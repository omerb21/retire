"""
Pydantic schemas for CurrentEmployer and EmployerGrant - Sprint 3
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from enum import Enum

class ActiveContinuityType(str, Enum):
    """Enum for active continuity types"""
    none = "none"
    severance = "severance"
    pension = "pension"

class GrantType(str, Enum):
    """Enum for grant types"""
    severance = "severance"
    adjustment = "adjustment"
    other = "other"

# CurrentEmployer schemas
class CurrentEmployerBase(BaseModel):
    employer_name: str = Field(..., description="שם המעסיק")
    employer_id_number: Optional[str] = Field(None, description="מספר זהות/ח.פ. של המעסיק")
    start_date: date = Field(..., description="תאריך תחילת עבודה")
    end_date: Optional[date] = Field(None, description="תאריך סיום עבודה (null אם עדיין עובד)")
    non_continuous_periods: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="תקופות לא רציפות")
    last_salary: Optional[float] = Field(None, description="שכר אחרון")
    average_salary: Optional[float] = Field(None, description="שכר ממוצע")
    severance_accrued: Optional[float] = Field(None, description="פיצויים שנצברו")
    # Frontend compatibility fields (mapped to existing DB fields)
    monthly_salary: Optional[float] = Field(None, description="שכר חודשי (ממופה ל-last_salary)")
    severance_balance: Optional[float] = Field(None, description="יתרת פיצויים (ממופה ל-severance_accrued)")
    other_grants: Optional[Dict[str, Any]] = Field(default_factory=dict, description="מענקים אחרים")
    tax_withheld: Optional[float] = Field(None, description="מס שנוכה")
    grant_installments: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="תשלומי מענק")
    active_continuity: Optional[ActiveContinuityType] = Field(None, description="רציפות פעילה")
    continuity_years: Optional[float] = Field(0.0, description="שנות רציפות")
    pre_retirement_pension: Optional[float] = Field(None, description="פנסיה לפני פרישה")
    existing_deductions: Optional[Dict[str, Any]] = Field(default_factory=dict, description="ניכויים קיימים")
    last_update: Optional[date] = Field(None, description="עדכון אחרון")

class CurrentEmployerCreate(CurrentEmployerBase):
    pass

class CurrentEmployerUpdate(BaseModel):
    employer_name: Optional[str] = None
    employer_id_number: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    non_continuous_periods: Optional[List[Dict[str, Any]]] = None
    last_salary: Optional[float] = None
    average_salary: Optional[float] = None
    severance_accrued: Optional[float] = None
    other_grants: Optional[Dict[str, Any]] = None
    tax_withheld: Optional[float] = None
    grant_installments: Optional[List[Dict[str, Any]]] = None
    active_continuity: Optional[ActiveContinuityType] = None
    continuity_years: Optional[float] = None
    pre_retirement_pension: Optional[float] = None
    existing_deductions: Optional[Dict[str, Any]] = None
    last_update: Optional[date] = None

class CurrentEmployerOut(CurrentEmployerBase):
    id: int
    client_id: int
    indexed_severance: Optional[float] = None
    severance_exemption_cap: Optional[float] = None
    severance_exempt: Optional[float] = None
    severance_taxable: Optional[float] = None
    severance_tax_due: Optional[float] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

# EmployerGrant schemas
class EmployerGrantBase(BaseModel):
    grant_type: GrantType = Field(..., description="סוג מענק")
    grant_amount: float = Field(..., description="סכום מענק")
    grant_date: date = Field(..., description="תאריך מענק")
    tax_withheld: Optional[float] = Field(0.0, description="מס שנוכה")

class EmployerGrantCreate(EmployerGrantBase):
    pass

class EmployerGrantOut(EmployerGrantBase):
    id: int
    employer_id: int
    grant_exempt: Optional[float] = None
    grant_taxable: Optional[float] = None
    tax_due: Optional[float] = None
    indexed_amount: Optional[float] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

# Response schemas for API endpoints
class GrantCalculationResult(BaseModel):
    """Result of grant calculation including tax breakdown"""
    grant_exempt: float = Field(..., description="חלק פטור ממס")
    grant_taxable: float = Field(..., description="חלק חייב במס")
    tax_due: float = Field(..., description="מס לתשלום")
    indexed_amount: float = Field(..., description="סכום מוצמד")
    service_years: float = Field(..., description="שנות ותק")
    severance_exemption_cap: float = Field(..., description="תקרת פטור פיצויים")

class GrantWithCalculation(EmployerGrantOut):
    """Grant with calculation results"""
    calculation: GrantCalculationResult

# Termination Decision schemas
class TerminationDecisionBase(BaseModel):
    """Base schema for termination decision"""
    termination_date: date = Field(..., description="תאריך סיום עבודה")
    use_employer_completion: bool = Field(False, description="האם תבוצע השלמת מעסיק")
    severance_amount: float = Field(..., description="סכום הפיצויים")
    # TODO: הפעל מחדש לאחר הרצת migration
    # severance_before_termination: Optional[float] = Field(None, description="סכום הפיצויים המקורי לפני עזיבה (כולל התפלגות)")
    exempt_amount: float = Field(..., description="סכום פטור ממס")
    taxable_amount: float = Field(..., description="סכום חייב במס")
    exempt_choice: str = Field(..., description="בחירה לחלק הפטור: redeem_with_exemption/redeem_no_exemption/annuity")
    taxable_choice: str = Field(..., description="בחירה לחלק החייב: redeem_no_exemption/annuity (פריסת מס אוטומטית ב-redeem_no_exemption)")
    tax_spread_years: Optional[int] = Field(None, description="מספר שנות פריסת מס")
    max_spread_years: Optional[int] = Field(None, description="מקסימום שנות פריסה מותרות")
    confirmed: Optional[bool] = Field(False, description="האם העזיבה אושרה והנתונים הוקפאו")
    source_accounts: Optional[str] = Field(None, description="רשימת שמות התכניות שמהן נלקחו הפיצויים (JSON)")

class TerminationDecisionCreate(TerminationDecisionBase):
    """Schema for creating termination decision"""
    pass

class TerminationDecisionOut(TerminationDecisionBase):
    """Schema for returning termination decision with results"""
    created_grant_id: Optional[int] = Field(None, description="ID של מענק שנוצר")
    created_pension_id: Optional[int] = Field(None, description="ID של קצבה שנוצרה")
    created_capital_asset_id: Optional[int] = Field(None, description="ID של נכס הון שנוצר")
    
    model_config = ConfigDict(from_attributes=True)
