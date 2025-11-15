from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CalculationCashFlowItem(BaseModel):
    """Single monthly cash flow row for the high-level calculation API."""

    year: int
    month: int
    gross_income: float
    tax_amount: float
    net_income: float
    asset_balances: Dict[str, float] = Field(default_factory=dict)


class CalculationSummary(BaseModel):
    """Aggregated totals over the entire cash flow horizon."""

    total_gross: float
    total_tax: float
    total_net: float
    final_balances: Dict[str, float] = Field(default_factory=dict)


class CalculationResult(BaseModel):
    """Result model returned to the frontend Results screen."""

    client_id: int
    scenario_name: Optional[str] = None
    case_number: int
    assumptions: Dict[str, Any]
    cash_flow: List[CalculationCashFlowItem]
    summary: CalculationSummary


class CalculationRequest(BaseModel):
    """Request model for running a high-level cash flow calculation."""

    client_id: int
    scenario_name: Optional[str] = None
    save_scenario: bool = False
    # Optional link to an existing Scenario row (for future use)
    scenario_id: Optional[int] = None
