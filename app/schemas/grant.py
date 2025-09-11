"""
Grant schema models for Pydantic validation
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import date, datetime
from decimal import Decimal

class GrantBase(BaseModel):
    employer_name: str = Field(..., description="שם המעסיק")
    work_start_date: Optional[date] = Field(None, description="תאריך התחלת עבודה")
    work_end_date: Optional[date] = Field(None, description="תאריך סיום עבודה")
    grant_type: Optional[str] = Field(default="severance", description="סוג המענק")
    grant_date: Optional[date] = Field(None, description="תאריך המענק")
    grant_amount: float = Field(..., description="סכום המענק", gt=0)
    service_years: Optional[float] = Field(None, description="שנות שירות")
    reason: Optional[str] = Field(None, description="סיבת המענק")

class GrantCreate(GrantBase):
    pass

class GrantUpdate(BaseModel):
    employer_name: Optional[str] = None
    work_start_date: Optional[date] = None
    work_end_date: Optional[date] = None
    grant_type: Optional[str] = None
    grant_date: Optional[date] = None
    grant_amount: Optional[float] = Field(None, gt=0)
    service_years: Optional[float] = Field(None, ge=0)
    reason: Optional[str] = None

class GrantCalculation(BaseModel):
    grant_exempt: float = Field(0, description="סכום פטור ממס")
    grant_taxable: float = Field(0, description="סכום חייב במס")
    tax_due: float = Field(0, description="מס לתשלום")

class GrantOut(GrantBase):
    id: int
    client_id: int
    
    model_config = ConfigDict(from_attributes=True)

class GrantWithCalculation(GrantOut):
    calculation: Optional[GrantCalculation] = None
