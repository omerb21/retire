"""
Client entity schemas for API request/response validation
"""
from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator, ConfigDict
from app.services.client_service import validate_id_number, normalize_id_number


class ClientBase(BaseModel):
    """Base schema for client data"""
    id_number_raw: str = Field(..., description="Raw ID number as entered by user")
    full_name: str = Field(..., description="Full name")
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


class ClientCreate(ClientBase):
    """Schema for creating a new client"""
    
    @field_validator('id_number_raw')
    @classmethod
    def validate_id(cls, v):
        """Validate ID number"""
        normalized = normalize_id_number(v)
        if not validate_id_number(normalized):
            raise ValueError("תעודת זהות אינה תקינה")
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

