# app/schemas/employment.py
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, field_serializer

class EmploymentBase(BaseModel):
    employer_name: str = Field(..., min_length=2, max_length=255)
    employer_reg_no: Optional[str] = Field(None, max_length=50)
    address_city: Optional[str] = Field(None, max_length=255)
    address_street: Optional[str] = Field(None, max_length=255)
    start_date: date

class EmploymentCreate(EmploymentBase):
    # current employment only (נוכחי)
    pass

class EmploymentOut(BaseModel):
    id: int
    client_id: int
    employer_id: int
    start_date: date
    end_date: Optional[date]
    is_current: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class TerminationPlanIn(BaseModel):
    planned_termination_date: date
    termination_reason: str  # use values of TerminationReason enum

class TerminationConfirmIn(BaseModel):
    actual_termination_date: date

class TerminationEventOut(BaseModel):
    id: int
    client_id: int
    employment_id: int
    reason: str
    planned_termination_date: Optional[date] = None
    actual_termination_date: Optional[date] = None
    created_at: datetime
    updated_at: datetime

    # Use from_attributes=True to map from ORM model
    model_config = ConfigDict(from_attributes=True)

    # Always convert reason to string value if it's an Enum
    @field_serializer("reason")
    def _ser_reason(self, v):
        if v is None:
            return None
        return getattr(v, "value", v)
