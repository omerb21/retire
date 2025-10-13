from pydantic import BaseModel, ConfigDict
from typing import Optional, Literal
from datetime import date

class PensionFundBase(BaseModel):
    fund_name: str
    fund_type: Optional[str] = None
    input_mode: Literal["calculated", "manual"]
    balance: Optional[float] = None
    annuity_factor: Optional[float] = None
    pension_amount: Optional[float] = None
    pension_start_date: Optional[date] = None
    indexation_method: Literal["none", "cpi", "fixed"]
    fixed_index_rate: Optional[float] = None
    remarks: Optional[str] = None
    deduction_file: Optional[str] = None
    conversion_source: Optional[str] = None  # JSON עם פרטי מקור ההמרה

class PensionFundCreate(PensionFundBase):
    client_id: int

class PensionFundUpdate(PensionFundBase):
    pass

class PensionFundOut(PensionFundBase):
    id: int
    client_id: int
    indexed_pension_amount: Optional[float] = None

    # Pydantic v2: במקום orm_mode=True
    model_config = ConfigDict(from_attributes=True)
