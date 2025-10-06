"""Pydantic schemas for Additional Income."""

from datetime import date
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field, validator

from app.models.additional_income import IncomeSourceType, PaymentFrequency, IndexationMethod, TaxTreatment


class AdditionalIncomeBase(BaseModel):
    """Base schema for Additional Income."""
    source_type: IncomeSourceType = Field(..., description="Type of income source")
    description: Optional[str] = Field(None, max_length=255, description="Description of the income source")
    amount: Decimal = Field(..., gt=0, description="Income amount")
    frequency: PaymentFrequency = Field(..., description="Payment frequency")
    start_date: date = Field(..., description="Income start date")
    end_date: Optional[date] = Field(None, description="Income end date")
    indexation_method: IndexationMethod = Field(IndexationMethod.NONE, description="Indexation method")
    fixed_rate: Optional[Decimal] = Field(None, ge=0, description="Fixed indexation rate")
    tax_treatment: TaxTreatment = Field(TaxTreatment.TAXABLE, description="Tax treatment")
    tax_rate: Optional[Decimal] = Field(None, ge=0, le=1, description="Tax rate for fixed rate tax")
    remarks: Optional[str] = Field(None, max_length=500, description="Additional remarks")

    @validator('end_date')
    def validate_end_date(cls, v, values):
        """Validate that end_date is after start_date."""
        if v is not None and 'start_date' in values and v < values['start_date']:
            raise ValueError('end_date must be after start_date')
        return v

    @validator('fixed_rate')
    def validate_fixed_rate(cls, v, values):
        """Validate fixed_rate is provided when indexation_method is fixed."""
        if 'indexation_method' in values and values['indexation_method'] == IndexationMethod.FIXED:
            if v is None:
                raise ValueError('fixed_rate is required when indexation_method is fixed')
        return v

    @validator('tax_rate')
    def validate_tax_rate(cls, v, values):
        """Validate tax_rate is provided when tax_treatment is fixed_rate."""
        if 'tax_treatment' in values and values['tax_treatment'] == TaxTreatment.FIXED_RATE:
            if v is None:
                raise ValueError('tax_rate is required when tax_treatment is fixed_rate')
        return v


class AdditionalIncomeCreate(AdditionalIncomeBase):
    """Schema for creating Additional Income."""
    pass


class AdditionalIncomeUpdate(BaseModel):
    """Schema for updating Additional Income."""
    source_type: Optional[IncomeSourceType] = None
    description: Optional[str] = Field(None, max_length=255)
    amount: Optional[Decimal] = Field(None, gt=0)
    frequency: Optional[PaymentFrequency] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    indexation_method: Optional[IndexationMethod] = None
    fixed_rate: Optional[Decimal] = Field(None, ge=0)
    tax_treatment: Optional[TaxTreatment] = None
    tax_rate: Optional[Decimal] = Field(None, ge=0, le=1)
    remarks: Optional[str] = Field(None, max_length=500)


class AdditionalIncomeResponse(AdditionalIncomeBase):
    """Schema for Additional Income response."""
    id: int
    client_id: int

    class Config:
        from_attributes = True


class AdditionalIncomeCashflowItem(BaseModel):
    """Schema for cashflow item from additional income."""
    date: date
    gross_amount: Decimal
    tax_amount: Decimal
    net_amount: Decimal
    source_type: IncomeSourceType
    description: Optional[str] = None
