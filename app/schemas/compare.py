from pydantic import BaseModel, validator, Field, root_validator
from typing import List, Literal, Optional


class ScenarioCompareRequest(BaseModel):
    scenarios: List[int]              # רשימת scenario_id
    from_: str = Field(alias="from")  # YYYY-MM
    to: str                           # YYYY-MM
    frequency: Literal["monthly"] = "monthly"

    class Config:
        populate_by_name = True

    @validator("from_")
    def v_from(cls, v):
        if not (len(v) == 7 and v[4] == '-' and v[:4].isdigit() and v[5:7].isdigit()):
            raise ValueError("from must be YYYY-MM format")
        return v

    @validator("to")
    def v_to(cls, v):
        if not (len(v) == 7 and v[4] == '-' and v[:4].isdigit() and v[5:7].isdigit()):
            raise ValueError("to must be YYYY-MM format")
        return v

    @validator("scenarios")
    def v_scenarios(cls, v):
        if not v or any((not isinstance(x, int) or x <= 0) for x in v):
            raise ValueError("scenarios must be a non-empty list of positive integers")
        return v

    @validator("frequency")
    def v_frequency(cls, v):
        if v != "monthly":
            raise ValueError("frequency must be 'monthly' - other frequencies not supported")
        return v

    @root_validator
    def validate_date_range(cls, values):
        from_ = values.get("from_")
        to = values.get("to")
        
        if from_ and to:
            # Convert YYYY-MM to comparable format
            from_year, from_month = map(int, from_.split('-'))
            to_year, to_month = map(int, to.split('-'))
            
            from_val = from_year * 12 + from_month
            to_val = to_year * 12 + to_month
            
            if from_val > to_val:
                raise ValueError("'from' date must be before or equal to 'to' date")
        
        return values
