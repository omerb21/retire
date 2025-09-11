"""
Pydantic schemas for Client API requests and responses
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class ClientBase(BaseModel):
    """Base client schema with common fields"""
    id_number_raw: str = Field(..., description="Raw ID number as entered")
    full_name: str = Field(..., description="Full name of the client")
    sex: Optional[str] = Field(None, description="Gender")
    marital_status: Optional[str] = Field(None, description="Marital status")
    address_city: Optional[str] = Field(None, description="City")
    address_street: Optional[str] = Field(None, description="Street")
    address_number: Optional[str] = Field(None, description="Street number")
    employer_name: Optional[str] = Field(None, description="Current employer name")

class ClientCreate(ClientBase):
    """Schema for creating a new client"""
    pass

class ClientUpdate(BaseModel):
    """Schema for updating an existing client"""
    full_name: Optional[str] = None
    sex: Optional[str] = None
    marital_status: Optional[str] = None
    address_city: Optional[str] = None
    address_street: Optional[str] = None
    address_number: Optional[str] = None
    employer_name: Optional[str] = None

class ClientResponse(ClientBase):
    """Schema for client API responses"""
    id: int
    id_number_normalized: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class ClientListResponse(BaseModel):
    """Schema for client list responses"""
    clients: list[ClientResponse]
    total: int
