from __future__ import annotations

from datetime import date
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, validator


class CashflowGenerateRequest(BaseModel):
    # "from" הוא שם שמור בפייתון; משתמשים ב-alias
    from_: str = Field(..., alias="from", description="YYYY-MM, e.g. 2025-01")
    to: str = Field(..., description="YYYY-MM, e.g. 2025-12")
    frequency: Literal["monthly"] = "monthly"
    
    @validator('from_', 'to')
    def validate_date_format(cls, v):
        if not isinstance(v, str) or len(v) != 7 or v[4] != "-":
            raise ValueError("Date must be in YYYY-MM format")
        try:
            year = int(v[0:4])
            month = int(v[5:7])
            if not (1 <= month <= 12):
                raise ValueError("Month must be between 01 and 12")
            if year < 1900 or year > 2100:
                raise ValueError("Year must be between 1900 and 2100")
        except ValueError as e:
            if "invalid literal" in str(e):
                raise ValueError("Date must be in YYYY-MM format with valid numbers")
            raise
        return v
    
    @validator('to')
    def validate_date_range(cls, v, values):
        # Range validation is handled in the service layer (generate_cashflow),
        # which raises ValueError mapped to HTTP 400. Here we only accept format.
        return v


class CashflowRow(BaseModel):
    date: date
    inflow: float
    outflow: float
    additional_income_net: float
    capital_return_net: float
    net: float
    # Optional detailed fields for additional incomes and capital assets
    additional_income_gross: float = 0.0
    additional_income_tax: float = 0.0
    additional_income_tax_for_total: float = 0.0
    capital_return_gross: float = 0.0
    capital_return_tax: float = 0.0


CashflowGenerateResponse = List[CashflowRow]


# ── integrate-all input schemas ──────────────────────────────────────

class ScenarioCashflowItem(BaseModel):
    """Single row in the flat-list format accepted by integrate-all."""
    date: str  # ISO date string, e.g. "2025-01-01"
    inflow: float
    outflow: float
    net: float

    class Config:
        extra = "allow"


class MonthlyCashflowItem(BaseModel):
    """Single row inside the *envelope* format returned by GET …/cashflow."""
    date: str
    income: float
    expenses: float
    net: float

    class Config:
        extra = "allow"


class CashflowEnvelope(BaseModel):
    """Envelope object that wraps a ``monthly`` list (GET cashflow shape)."""
    monthly: List[MonthlyCashflowItem]

    class Config:
        extra = "allow"
