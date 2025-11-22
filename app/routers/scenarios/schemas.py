"""
Pydantic schemas for scenarios
"""
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime


class ScenarioBase(BaseModel):
    """Base schema for scenario"""
    name: str
    description: Optional[str] = None
    parameters: str = Field(default="{}", description="JSON parameters for scenario")


class ScenarioCreate(BaseModel):
    """Schema for creating a new scenario"""
    name: str
    description: Optional[str] = None


class ScenarioUpdate(ScenarioBase):
    """Schema for updating a scenario"""
    name: Optional[str] = None
    parameters: Optional[str] = None


class ScenarioResponse(BaseModel):
    """Schema for scenario response"""
    id: int
    client_id: int
    name: str
    description: Optional[str] = None
    parameters: str = "{}"
    cashflow_projection: Optional[str] = None
    summary_results: Optional[str] = None
    created_at: datetime
    
    @classmethod
    def from_db_scenario(cls, db_scenario):
        """Convert DB model to response schema"""
        return cls(
            id=db_scenario.id,
            client_id=db_scenario.client_id,
            name=db_scenario.scenario_name,
            description=None,  # Not stored in DB
            parameters=db_scenario.parameters or "{}",
            cashflow_projection=db_scenario.cashflow_projection,
            summary_results=db_scenario.summary_results,
            created_at=db_scenario.created_at
        )
    
    class Config:
        from_attributes = True


class RetirementScenariosRequest(BaseModel):
    """Request schema for retirement scenarios"""
    retirement_age: int = Field(..., ge=50, le=80, description="גיל פרישה מבוקש")
    pension_portfolio: Optional[List[dict]] = Field(default=None, description="נתוני תיק פנסיוני (אופציונלי)")
    include_current_employer_termination: Optional[bool] = Field(
        default=False,
        description="האם לכלול סיום עבודה מהמעסיק הנוכחי בתרחישים",
    )
