"""Pydantic schemas for Capital Asset."""

from datetime import date
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field, validator

from app.models.capital_asset import AssetType, PaymentFrequency, IndexationMethod, TaxTreatment


class CapitalAssetBase(BaseModel):
    """Base schema for Capital Asset."""
    asset_name: Optional[str] = Field(None, max_length=255, description="Asset name")
    asset_type: AssetType = Field(..., description="Type of capital asset")
    description: Optional[str] = Field(None, max_length=255, description="Description of the asset")
    current_value: Decimal = Field(..., gt=0, description="Current asset value")
    monthly_income: Optional[Decimal] = Field(None, ge=0, description="Monthly income from asset")
    rental_income: Optional[Decimal] = Field(None, ge=0, description="Rental income (legacy)")
    monthly_rental_income: Optional[Decimal] = Field(None, ge=0, description="Monthly rental income (legacy)")
    annual_return_rate: Decimal = Field(..., ge=0, description="Annual return rate")
    payment_frequency: PaymentFrequency = Field(..., description="Payment frequency")
    start_date: date = Field(..., description="Asset start date")
    end_date: Optional[date] = Field(None, description="Asset end date")
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


class CapitalAssetCreate(CapitalAssetBase):
    """Schema for creating Capital Asset."""
    pass


class CapitalAssetUpdate(BaseModel):
    """Schema for updating Capital Asset."""
    asset_type: Optional[AssetType] = None
    description: Optional[str] = Field(None, max_length=255)
    current_value: Optional[Decimal] = Field(None, gt=0)
    annual_return_rate: Optional[Decimal] = Field(None, ge=0)
    payment_frequency: Optional[PaymentFrequency] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    indexation_method: Optional[IndexationMethod] = None
    fixed_rate: Optional[Decimal] = Field(None, ge=0)
    tax_treatment: Optional[TaxTreatment] = None
    tax_rate: Optional[Decimal] = Field(None, ge=0, le=1)
    remarks: Optional[str] = Field(None, max_length=500)


class CapitalAssetResponse(CapitalAssetBase):
    """Schema for Capital Asset response."""
    id: int
    client_id: int

    class Config:
        from_attributes = True


class CapitalAssetCashflowItem(BaseModel):
    """Schema for cashflow item from capital asset."""
    date: date
    gross_return: Decimal
    tax_amount: Decimal
    net_return: Decimal
    asset_type: AssetType
    description: Optional[str] = None
