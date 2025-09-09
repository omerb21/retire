"""
Pydantic schemas for API request/response models
"""
from datetime import date, datetime
from typing import Optional, List, Dict, Any
from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


# Enums
class ActiveContinuityType(str, Enum):
    none = "none"
    severance = "severance"
    pension = "pension"


class GrantType(str, Enum):
    severance = "severance"
    adjustment = "adjustment"
    other = "other"


class InputMode(str, Enum):
    calculated = "calculated"
    manual = "manual"


class IndexationMethod(str, Enum):
    none = "none"
    cpi = "cpi"
    fixed = "fixed"


# Base schemas
class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# Client schemas
class ClientBase(BaseSchema):
    id_number: str = Field(..., min_length=9, max_length=9, description="Israeli ID number")
    full_name: str = Field(..., min_length=1, max_length=100)
    first_name: Optional[str] = Field(None, max_length=50)
    last_name: Optional[str] = Field(None, max_length=50)
    birth_date: date
    gender: Optional[str] = Field(None, max_length=10)
    marital_status: Optional[str] = Field(None, max_length=20)
    self_employed: bool = False
    current_employer_exists: bool = False
    planned_termination_date: Optional[date] = None
    email: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    address_street: Optional[str] = Field(None, max_length=100)
    address_city: Optional[str] = Field(None, max_length=50)
    address_postal_code: Optional[str] = Field(None, max_length=10)
    retirement_target_date: Optional[date] = None
    notes: Optional[str] = None


class ClientCreate(ClientBase):
    pass


class ClientUpdate(BaseSchema):
    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    first_name: Optional[str] = Field(None, max_length=50)
    last_name: Optional[str] = Field(None, max_length=50)
    birth_date: Optional[date] = None
    gender: Optional[str] = Field(None, max_length=10)
    marital_status: Optional[str] = Field(None, max_length=20)
    self_employed: Optional[bool] = None
    current_employer_exists: Optional[bool] = None
    planned_termination_date: Optional[date] = None
    email: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    address_street: Optional[str] = Field(None, max_length=100)
    address_city: Optional[str] = Field(None, max_length=50)
    address_postal_code: Optional[str] = Field(None, max_length=10)
    retirement_target_date: Optional[date] = None
    notes: Optional[str] = None


class Client(ClientBase):
    id: int
    id_number_raw: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


# Current Employer schemas
class CurrentEmployerBase(BaseSchema):
    employer_name: str = Field(..., min_length=1, max_length=255)
    employer_id_number: Optional[str] = Field(None, max_length=50)
    start_date: date
    end_date: Optional[date] = None
    non_continuous_periods: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    last_salary: Optional[Decimal] = Field(None, ge=0)
    average_salary: Optional[Decimal] = Field(None, ge=0)
    severance_accrued: Optional[Decimal] = Field(None, ge=0)
    other_grants: Optional[Dict[str, Any]] = Field(default_factory=dict)
    tax_withheld: Optional[Decimal] = Field(None, ge=0)
    grant_installments: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    active_continuity: ActiveContinuityType = ActiveContinuityType.none
    continuity_years: Decimal = Field(default=Decimal("0.0"), ge=0)
    pre_retirement_pension: Optional[Decimal] = Field(None, ge=0)
    existing_deductions: Optional[Dict[str, Any]] = Field(default_factory=dict)


class CurrentEmployerCreate(CurrentEmployerBase):
    client_id: int


class CurrentEmployerUpdate(BaseSchema):
    employer_name: Optional[str] = Field(None, min_length=1, max_length=255)
    employer_id_number: Optional[str] = Field(None, max_length=50)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    non_continuous_periods: Optional[List[Dict[str, Any]]] = None
    last_salary: Optional[Decimal] = Field(None, ge=0)
    average_salary: Optional[Decimal] = Field(None, ge=0)
    severance_accrued: Optional[Decimal] = Field(None, ge=0)
    other_grants: Optional[Dict[str, Any]] = None
    tax_withheld: Optional[Decimal] = Field(None, ge=0)
    grant_installments: Optional[List[Dict[str, Any]]] = None
    active_continuity: Optional[ActiveContinuityType] = None
    continuity_years: Optional[Decimal] = Field(None, ge=0)
    pre_retirement_pension: Optional[Decimal] = Field(None, ge=0)
    existing_deductions: Optional[Dict[str, Any]] = None


class CurrentEmployer(CurrentEmployerBase):
    id: int
    client_id: int
    last_update: date
    indexed_severance: Optional[Decimal] = None
    severance_exemption_cap: Optional[Decimal] = None
    severance_exempt: Optional[Decimal] = None
    severance_taxable: Optional[Decimal] = None
    severance_tax_due: Optional[Decimal] = None
    created_at: datetime
    updated_at: datetime


# Grant schemas
class GrantBase(BaseSchema):
    employer_name: Optional[str] = Field(None, max_length=200)
    work_start_date: Optional[date] = None
    work_end_date: Optional[date] = None
    grant_amount: Optional[Decimal] = Field(None, ge=0)
    grant_date: Optional[date] = None
    grant_indexed_amount: Optional[Decimal] = Field(None, ge=0)
    limited_indexed_amount: Optional[Decimal] = Field(None, ge=0)
    grant_ratio: Optional[Decimal] = Field(None, ge=0, le=1)
    impact_on_exemption: Optional[Decimal] = None


class GrantCreate(GrantBase):
    client_id: int


class GrantUpdate(GrantBase):
    pass


class Grant(GrantBase):
    id: int
    client_id: int
    created_at: datetime
    updated_at: datetime


# Employer Grant schemas
class EmployerGrantBase(BaseSchema):
    grant_type: GrantType
    grant_amount: Decimal = Field(..., gt=0)
    grant_date: date
    tax_withheld: Decimal = Field(default=Decimal("0.0"), ge=0)


class EmployerGrantCreate(EmployerGrantBase):
    employer_id: int


class EmployerGrantUpdate(BaseSchema):
    grant_type: Optional[GrantType] = None
    grant_amount: Optional[Decimal] = Field(None, gt=0)
    grant_date: Optional[date] = None
    tax_withheld: Optional[Decimal] = Field(None, ge=0)


class EmployerGrant(EmployerGrantBase):
    id: int
    employer_id: int
    grant_exempt: Optional[Decimal] = None
    grant_taxable: Optional[Decimal] = None
    tax_due: Optional[Decimal] = None
    indexed_amount: Optional[Decimal] = None
    created_at: datetime
    updated_at: datetime


# Pension Fund schemas
class PensionFundBase(BaseSchema):
    fund_name: str = Field(..., min_length=1, max_length=200)
    fund_type: Optional[str] = Field(None, max_length=50)
    input_mode: InputMode
    balance: Optional[Decimal] = Field(None, ge=0)
    annuity_factor: Optional[Decimal] = Field(None, gt=0)
    pension_amount: Optional[Decimal] = Field(None, ge=0)
    pension_start_date: Optional[date] = None
    indexation_method: IndexationMethod = IndexationMethod.none
    fixed_index_rate: Optional[Decimal] = Field(None, ge=0)
    indexed_pension_amount: Optional[Decimal] = Field(None, ge=0)
    remarks: Optional[str] = Field(None, max_length=500)


class PensionFundCreate(PensionFundBase):
    client_id: int


class PensionFundUpdate(BaseSchema):
    fund_name: Optional[str] = Field(None, min_length=1, max_length=200)
    fund_type: Optional[str] = Field(None, max_length=50)
    input_mode: Optional[InputMode] = None
    balance: Optional[Decimal] = Field(None, ge=0)
    annuity_factor: Optional[Decimal] = Field(None, gt=0)
    pension_amount: Optional[Decimal] = Field(None, ge=0)
    pension_start_date: Optional[date] = None
    indexation_method: Optional[IndexationMethod] = None
    fixed_index_rate: Optional[Decimal] = Field(None, ge=0)
    indexed_pension_amount: Optional[Decimal] = Field(None, ge=0)
    remarks: Optional[str] = Field(None, max_length=500)


class PensionFund(PensionFundBase):
    id: int
    client_id: int
    created_at: datetime
    updated_at: datetime


# Scenario schemas
class ScenarioBase(BaseSchema):
    scenario_name: str = Field(..., min_length=1, max_length=255)
    apply_tax_planning: bool = False
    apply_capitalization: bool = False
    apply_exemption_shield: bool = False
    parameters: str = Field(default="{}")
    summary_results: Optional[str] = None
    cashflow_projection: Optional[str] = None


class ScenarioCreate(ScenarioBase):
    client_id: int


class ScenarioUpdate(BaseSchema):
    scenario_name: Optional[str] = Field(None, min_length=1, max_length=255)
    apply_tax_planning: Optional[bool] = None
    apply_capitalization: Optional[bool] = None
    apply_exemption_shield: Optional[bool] = None
    parameters: Optional[str] = None
    summary_results: Optional[str] = None
    cashflow_projection: Optional[str] = None


class Scenario(ScenarioBase):
    id: int
    client_id: int
    created_at: datetime


# Response schemas
class ClientWithEmployer(Client):
    current_employers: List[CurrentEmployer] = []
    grants: List[Grant] = []
    pension_funds: List[PensionFund] = []


class APIResponse(BaseSchema):
    success: bool
    message: str
    data: Optional[Any] = None


class ErrorResponse(BaseSchema):
    success: bool = False
    message: str
    detail: Optional[str] = None
