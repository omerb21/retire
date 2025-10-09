"""
Client entity schemas for API request/response validation
"""
from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator, ConfigDict
from app.services.client_service import validate_id_number, normalize_id_number


class ClientBase(BaseModel):
    """Base schema for client data"""
    id_number_raw: Optional[str] = Field(None, description="Raw ID number as entered by user")
    full_name: Optional[str] = Field(None, description="Full name")
    first_name: Optional[str] = Field(None, description="First name")
    last_name: Optional[str] = Field(None, description="Last name")
    birth_date: date = Field(..., description="Birth date")
    gender: Optional[str] = Field(None, description="Gender (male, female, other)")
    marital_status: Optional[str] = Field(None, description="Marital status")
    self_employed: Optional[bool] = Field(False, description="Is self-employed")
    current_employer_exists: Optional[bool] = Field(False, description="Has current employer")
    planned_termination_date: Optional[date] = Field(None, description="Planned termination date with current employer")
    email: Optional[str] = Field(None, description="Email address")
    phone: Optional[str] = Field(None, description="Phone number")
    address_street: Optional[str] = Field(None, description="Street address")
    address_city: Optional[str] = Field(None, description="City")
    address_postal_code: Optional[str] = Field(None, description="Postal code")
    retirement_target_date: Optional[date] = Field(None, description="Target retirement date")
    is_active: bool = Field(True, description="Is client active")
    notes: Optional[str] = Field(None, description="Notes")
    
    # Tax-related fields
    num_children: Optional[int] = Field(None, description="Number of children")
    is_new_immigrant: Optional[bool] = Field(None, description="Is new immigrant")
    is_veteran: Optional[bool] = Field(None, description="Is veteran")
    is_disabled: Optional[bool] = Field(None, description="Is disabled")
    disability_percentage: Optional[int] = Field(None, description="Disability percentage")
    is_student: Optional[bool] = Field(None, description="Is student")
    reserve_duty_days: Optional[int] = Field(None, description="Reserve duty days")
    
    # Income and deductions
    annual_salary: Optional[float] = Field(None, description="Annual salary")
    pension_contributions: Optional[float] = Field(None, description="Pension contributions")
    study_fund_contributions: Optional[float] = Field(None, description="Study fund contributions")
    insurance_premiums: Optional[float] = Field(None, description="Insurance premiums")
    charitable_donations: Optional[float] = Field(None, description="Charitable donations")
    
    # Tax credit points and pension
    tax_credit_points: Optional[float] = Field(None, description="Tax credit points")
    pension_start_date: Optional[date] = Field(None, description="Pension start date")
    spouse_income: Optional[float] = Field(None, description="Spouse income")
    immigration_date: Optional[date] = Field(None, description="Immigration date")
    military_discharge_date: Optional[date] = Field(None, description="Military discharge date")


class ClientCreate(ClientBase):
    """Schema for creating a new client"""
    id_number: Optional[str] = Field(None, description="ID number (for backward compatibility)")
    
    @field_validator('id_number_raw')
    @classmethod
    def validate_id_raw(cls, v, values):
        """Validate ID number raw if provided"""
        if v is not None:
            normalized = normalize_id_number(v)
            if not validate_id_number(normalized):
                raise ValueError("תעודת זהות אינה תקינה")
            return v
        return v
        
    @field_validator('id_number')
    @classmethod
    def validate_id(cls, v, values):
        """Validate ID number and set id_number_raw if needed"""
        if v is not None:
            normalized = normalize_id_number(v)
            if not validate_id_number(normalized):
                raise ValueError("תעודת זהות אינה תקינה")
            # If id_number is provided but id_number_raw is not, use id_number for id_number_raw
            values.data["id_number_raw"] = v
        return v
        
    @field_validator('full_name')
    @classmethod
    def set_full_name(cls, v, values):
        """Set full_name from first_name and last_name if not provided"""
        if v is None and values.data.get('first_name') and values.data.get('last_name'):
            return f"{values.data['first_name']} {values.data['last_name']}"
        return v


class ClientUpdate(BaseModel):
    """Schema for updating an existing client"""
    id_number_raw: Optional[str] = Field(None, description="Raw ID number as entered by user")
    full_name: Optional[str] = Field(None, description="Full name")
    first_name: Optional[str] = Field(None, description="First name")
    last_name: Optional[str] = Field(None, description="Last name")
    birth_date: Optional[date] = Field(None, description="Birth date")
    gender: Optional[str] = Field(None, description="Gender (male, female, other)")
    marital_status: Optional[str] = Field(None, description="Marital status")
    self_employed: Optional[bool] = Field(None, description="Is self-employed")
    current_employer_exists: Optional[bool] = Field(None, description="Has current employer")
    planned_termination_date: Optional[date] = Field(None, description="Planned termination date with current employer")
    email: Optional[str] = Field(None, description="Email address")
    phone: Optional[str] = Field(None, description="Phone number")
    address_street: Optional[str] = Field(None, description="Street address")
    address_city: Optional[str] = Field(None, description="City")
    address_postal_code: Optional[str] = Field(None, description="Postal code")
    retirement_target_date: Optional[date] = Field(None, description="Target retirement date")
    is_active: Optional[bool] = Field(None, description="Is client active")
    notes: Optional[str] = Field(None, description="Notes")
    
    # Tax-related fields
    num_children: Optional[int] = Field(None, description="Number of children")
    is_new_immigrant: Optional[bool] = Field(None, description="Is new immigrant")
    is_veteran: Optional[bool] = Field(None, description="Is veteran")
    is_disabled: Optional[bool] = Field(None, description="Is disabled")
    disability_percentage: Optional[int] = Field(None, description="Disability percentage")
    is_student: Optional[bool] = Field(None, description="Is student")
    reserve_duty_days: Optional[int] = Field(None, description="Reserve duty days")
    
    # Income and deductions
    annual_salary: Optional[float] = Field(None, description="Annual salary")
    pension_contributions: Optional[float] = Field(None, description="Pension contributions")
    study_fund_contributions: Optional[float] = Field(None, description="Study fund contributions")
    insurance_premiums: Optional[float] = Field(None, description="Insurance premiums")
    charitable_donations: Optional[float] = Field(None, description="Charitable donations")
    
    # Tax credit points and pension
    tax_credit_points: Optional[float] = Field(None, description="Tax credit points")
    pension_start_date: Optional[date] = Field(None, description="Pension start date")
    spouse_income: Optional[float] = Field(None, description="Spouse income")
    immigration_date: Optional[date] = Field(None, description="Immigration date")
    military_discharge_date: Optional[date] = Field(None, description="Military discharge date")
    
    @field_validator('id_number_raw')
    @classmethod
    def validate_id_update(cls, v):
        """Validate ID number if provided"""
        if v:
            normalized = normalize_id_number(v)
            if not validate_id_number(normalized):
                raise ValueError("תעודת זהות אינה תקינה")
        return v


class ClientResponse(ClientBase):
    """Schema for client response"""
    id: int
    id_number: str
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class ClientList(BaseModel):
    """Schema for list of clients"""
    items: List[ClientResponse]
    total: int
    page: int
    page_size: int

