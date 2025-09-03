from pydantic import BaseModel, Field, validator
from typing import Dict, Literal, Optional


class ReportPdfRequest(BaseModel):
    """Request schema for PDF report generation"""
    from_: str = Field(..., alias="from", description="YYYY-MM, e.g. 2025-01")
    to: str = Field(..., description="YYYY-MM, e.g. 2025-12")
    frequency: Literal["monthly"] = "monthly"
    sections: Dict[str, bool] = {
        "summary": True,
        "cashflow_table": True,
        "net_chart": True,
        "scenarios_compare": True
    }

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
        if 'from_' in values and v < values['from_']:
            raise ValueError("'to' date must be greater than or equal to 'from' date")
        return v

    @validator("sections", pre=True)
    def set_default_sections(cls, v):
        """Set default values for sections if not provided"""
        if v is None:
            v = {}
        defaults = {
            "summary": True,
            "cashflow_table": True,
            "net_chart": True,
            "scenarios_compare": True
        }
        defaults.update(v)
        return defaults
