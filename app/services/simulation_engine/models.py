from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any, Optional, Union

from pydantic import BaseModel, Field, field_validator


class SelectedSource(str, Enum):
    DB = "db"
    SNAPSHOT = "snapshot"
    MANUAL = "manual"


class ComparisonMode(str, Enum):
    NONE = "none"
    CURRENT_VS_CONVERTED = "current_vs_converted"
    CONVERTED_ONLY = "converted_only"


class ConversionActionType(str, Enum):
    CONVERT = "convert"
    SPLIT = "split"
    MERGE = "merge"
    WITHDRAW = "withdraw"


class MonthlyCashflowItem(BaseModel):
    month: date
    gross: float
    net: float
    components: dict[str, float]

    @field_validator("month")
    @classmethod
    def _month_must_be_first_of_month(cls, v: date) -> date:
        if v.day != 1:
            raise ValueError("month must be the first day of the month")
        return v


class TaxBreakdown(BaseModel):
    taxable_income_monthly: Optional[float] = None
    tax_monthly: Optional[float] = None
    notes: list[str] = Field(default_factory=list)


class SustainabilityMetrics(BaseModel):
    is_sustainable: Optional[bool] = None
    depletion_month: Optional[date] = None
    notes: list[str] = Field(default_factory=list)


class ConvertedTarget(BaseModel):
    target_id: str
    target_type: str
    amount: Optional[float] = None
    meta: dict[str, str] = Field(default_factory=dict)


class ConversionAction(BaseModel):
    action_type: ConversionActionType
    source_id: Optional[str] = None
    target_id: Optional[str] = None
    parameters: dict[str, float] = Field(default_factory=dict)


class ConversionPlan(BaseModel):
    actions: list[ConversionAction] = Field(default_factory=list)


class ScenarioParameters(BaseModel):
    assumptions: dict[str, float] = Field(default_factory=dict)
    overrides: dict[str, float] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class SimulationRequest(BaseModel):
    client_id: int
    retirement_date: date
    selected_sources: list[SelectedSource]
    scenario_parameters: ScenarioParameters
    comparison_mode: Optional[ComparisonMode] = None
    conversion_plan: Optional[ConversionPlan] = None


RawCalculationValue = Union[int, float, str, bool, None]


class SimulationResult(BaseModel):
    converted_targets: list[ConvertedTarget] = Field(default_factory=list)
    monthly_cashflow: list[MonthlyCashflowItem]
    tax_breakdown: TaxBreakdown
    exempt_pension_component: dict[str, float] = Field(default_factory=dict)
    sustainability_metrics: SustainabilityMetrics
    raw_calculation_map: dict[str, RawCalculationValue] = Field(default_factory=dict)

    @field_validator("raw_calculation_map")
    @classmethod
    def _raw_calc_map_must_be_flat_simple_types(
        cls, v: dict[str, Any]
    ) -> dict[str, RawCalculationValue]:
        if not isinstance(v, dict):
            raise TypeError("raw_calculation_map must be a dict")
        for key, value in v.items():
            if (
                isinstance(value, dict)
                or isinstance(value, list)
                or isinstance(value, tuple)
                or isinstance(value, set)
            ):
                raise ValueError(
                    "raw_calculation_map values must be flat primitive types (no nested dict/list)"
                )
            if not isinstance(value, (int, float, str, bool)) and value is not None:
                raise ValueError(
                    "raw_calculation_map values must be int|float|str|bool|None"
                )
        return v
