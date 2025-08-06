from datetime import date, datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class ScenarioIn(BaseModel):
    # פרמטרים עיקריים לתרחיש חישוב
    planned_termination_date: Optional[date] = None
    retirement_age: Optional[int] = Field(None, ge=50, le=90)
    monthly_expenses: Optional[float] = Field(None, ge=0)
    other_incomes_monthly: Optional[float] = Field(None, ge=0)

class CashflowPoint(BaseModel):
    date: date
    inflow: float
    outflow: float
    net: float

class ScenarioOut(BaseModel):
    # תקציר תוצאות
    seniority_years: float
    grant_gross: float
    grant_exempt: float
    grant_tax: float
    grant_net: float
    pension_monthly: float
    indexation_factor: float
    cashflow: List[CashflowPoint]

class ScenarioCreateIn(BaseModel):
    # יצירת תרחיש חדש עם שם
    scenario_name: str = Field(..., min_length=1, max_length=255)
    planned_termination_date: Optional[date] = None
    monthly_expenses: Optional[float] = Field(None, ge=0)
    # Planning flags
    apply_tax_planning: bool = False
    apply_capitalization: bool = False
    apply_exemption_shield: bool = False
    # Additional parameters
    other_parameters: Dict[str, Any] = Field(default_factory=dict)

class ScenarioCreateResponse(BaseModel):
    # תגובה פשוטה ליצירת תרחיש
    scenario_id: int

class ScenarioCreateOut(BaseModel):
    # תגובה ליצירת תרחיש + תוצאות חישוב
    scenario_id: int
    seniority_years: float
    grant_gross: float
    grant_exempt: float
    grant_tax: float
    grant_net: float
    pension_monthly: float
    indexation_factor: float
    cashflow: List[CashflowPoint]

class ScenarioListItem(BaseModel):
    # פריט ברשימת תרחישים
    id: int
    scenario_name: str
    apply_tax_planning: bool
    apply_capitalization: bool
    apply_exemption_shield: bool
    created_at: datetime

class ScenarioListOut(BaseModel):
    # רשימת תרחישים
    scenarios: List[ScenarioListItem]
