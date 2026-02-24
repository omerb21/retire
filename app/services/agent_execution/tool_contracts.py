from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, ValidationError


@dataclass(frozen=True)
class ToolContract:
    tool_name: str
    args_model: type[BaseModel] | None
    result_model: type[BaseModel] | None
    notes: str | None = None


class _EmptyArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _GetClientSnapshotResult(BaseModel):
    success: bool
    tool_name: str
    total_items: int
    breakdown: dict

    model_config = ConfigDict(extra="allow")


class _GetSystemNumericConstantsResult(BaseModel):
    success: bool
    tool_name: str
    result: dict

    model_config = ConfigDict(extra="allow")


class _MonthlyPensionSummaryResult(BaseModel):
    reply: str
    computed_data: dict
    computed_data_marker: str

    model_config = ConfigDict(extra="allow")


_CONTRACTS: dict[str, ToolContract] = {
    "GET_CLIENT_SNAPSHOT": ToolContract(
        tool_name="GET_CLIENT_SNAPSHOT",
        args_model=_EmptyArgs,
        result_model=_GetClientSnapshotResult,
        notes="Stable deterministic tool. Args must be empty.",
    ),
    "GET_SYSTEM_NUMERIC_CONSTANTS": ToolContract(
        tool_name="GET_SYSTEM_NUMERIC_CONSTANTS",
        args_model=_EmptyArgs,
        result_model=_GetSystemNumericConstantsResult,
        notes="Read-only tool used in tests.",
    ),
    "MONTHLY_PENSION_SUMMARY": ToolContract(
        tool_name="MONTHLY_PENSION_SUMMARY",
        args_model=_EmptyArgs,
        result_model=_MonthlyPensionSummaryResult,
        notes="Deterministic monthly pension summary tool. Args must be empty.",
    ),
    "GET_PENSION_PRODUCTS": ToolContract(
        tool_name="GET_PENSION_PRODUCTS",
        args_model=None,
        result_model=None,
        notes=None,
    ),
    "GET_ACCOUNT_DETAILS": ToolContract(
        tool_name="GET_ACCOUNT_DETAILS",
        args_model=None,
        result_model=None,
        notes=None,
    ),
    "GET_TAX_PROJECTION": ToolContract(
        tool_name="GET_TAX_PROJECTION",
        args_model=None,
        result_model=None,
        notes=None,
    ),
    "RUN_RETIREMENT_CASHFLOW_ANALYSIS": ToolContract(
        tool_name="RUN_RETIREMENT_CASHFLOW_ANALYSIS",
        args_model=None,
        result_model=None,
        notes=None,
    ),
    "RUN_RETIREMENT_SCENARIOS": ToolContract(
        tool_name="RUN_RETIREMENT_SCENARIOS",
        args_model=None,
        result_model=None,
        notes=None,
    ),
    "RUN_RETIREMENT_SCENARIOS_PREVIEW": ToolContract(
        tool_name="RUN_RETIREMENT_SCENARIOS_PREVIEW",
        args_model=None,
        result_model=None,
        notes=None,
    ),
    "FIND_OPTIMAL_SCENARIO": ToolContract(
        tool_name="FIND_OPTIMAL_SCENARIO",
        args_model=None,
        result_model=None,
        notes=None,
    ),
    "SELECT_TARGET_PENSION_SCENARIO": ToolContract(
        tool_name="SELECT_TARGET_PENSION_SCENARIO",
        args_model=None,
        result_model=None,
        notes=None,
    ),
    "EXECUTE_RETIREMENT_SCENARIO": ToolContract(
        tool_name="EXECUTE_RETIREMENT_SCENARIO",
        args_model=None,
        result_model=None,
        notes=None,
    ),
    "BUILD_TARGET_PENSION_PLAN": ToolContract(
        tool_name="BUILD_TARGET_PENSION_PLAN",
        args_model=None,
        result_model=None,
        notes=None,
    ),
    "PROJECT_TOTAL_ANNUITY": ToolContract(
        tool_name="PROJECT_TOTAL_ANNUITY",
        args_model=None,
        result_model=None,
        notes=None,
    ),
    "CALCULATE_PENSION_COMMUTATION": ToolContract(
        tool_name="CALCULATE_PENSION_COMMUTATION",
        args_model=None,
        result_model=None,
        notes=None,
    ),
    "EXECUTE_PENSION_COMMUTATION": ToolContract(
        tool_name="EXECUTE_PENSION_COMMUTATION",
        args_model=None,
        result_model=None,
        notes=None,
    ),
    "SUBMIT_TAX_COMMUTATION": ToolContract(
        tool_name="SUBMIT_TAX_COMMUTATION",
        args_model=None,
        result_model=None,
        notes=None,
    ),
    "CALCULATE_TAX_EXEMPT_PENSION": ToolContract(
        tool_name="CALCULATE_TAX_EXEMPT_PENSION",
        args_model=None,
        result_model=None,
        notes=None,
    ),
    "CALCULATE_CAPITAL_WITHDRAWAL_TAX": ToolContract(
        tool_name="CALCULATE_CAPITAL_WITHDRAWAL_TAX",
        args_model=None,
        result_model=None,
        notes=None,
    ),
    "CALCULATE_TAX_SPREAD_BENEFIT": ToolContract(
        tool_name="CALCULATE_TAX_SPREAD_BENEFIT",
        args_model=None,
        result_model=None,
        notes=None,
    ),
    "CALCULATE_FIXATION_OF_RIGHTS": ToolContract(
        tool_name="CALCULATE_FIXATION_OF_RIGHTS",
        args_model=None,
        result_model=None,
        notes=None,
    ),
    "GET_FIXATION_STATUS_SNAPSHOT": ToolContract(
        tool_name="GET_FIXATION_STATUS_SNAPSHOT",
        args_model=None,
        result_model=None,
        notes=None,
    ),
    "CHECK_DATA_COMPLETENESS": ToolContract(
        tool_name="CHECK_DATA_COMPLETENESS",
        args_model=None,
        result_model=None,
        notes=None,
    ),
    "TRANSFORM_FUNDS_TO_ASSETS": ToolContract(
        tool_name="TRANSFORM_FUNDS_TO_ASSETS",
        args_model=None,
        result_model=None,
        notes=None,
    ),
    "CREATE_TAX_EXEMPT_GRANT": ToolContract(
        tool_name="CREATE_TAX_EXEMPT_GRANT",
        args_model=None,
        result_model=None,
        notes=None,
    ),
    "CREATE_ADDITIONAL_INCOME": ToolContract(
        tool_name="CREATE_ADDITIONAL_INCOME",
        args_model=None,
        result_model=None,
        notes=None,
    ),
    "CREATE_INDIVIDUAL_ASSET": ToolContract(
        tool_name="CREATE_INDIVIDUAL_ASSET",
        args_model=None,
        result_model=None,
        notes=None,
    ),
    "SET_CURRENT_EMPLOYER_DETAILS": ToolContract(
        tool_name="SET_CURRENT_EMPLOYER_DETAILS",
        args_model=None,
        result_model=None,
        notes=None,
    ),
    "EXECUTE_WORK_TERMINATION": ToolContract(
        tool_name="EXECUTE_WORK_TERMINATION",
        args_model=None,
        result_model=None,
        notes=None,
    ),
    "PROCESS_TERMINATION": ToolContract(
        tool_name="PROCESS_TERMINATION",
        args_model=None,
        result_model=None,
        notes=None,
    ),
    "GENERATE_FULL_REPORT": ToolContract(
        tool_name="GENERATE_FULL_REPORT",
        args_model=None,
        result_model=None,
        notes=None,
    ),
    "GENERATE_TAX_DEDUCTION_DOCUMENTS": ToolContract(
        tool_name="GENERATE_TAX_DEDUCTION_DOCUMENTS",
        args_model=None,
        result_model=None,
        notes=None,
    ),
    "GET_SYSTEM_STATE_SNAPSHOT": ToolContract(
        tool_name="GET_SYSTEM_STATE_SNAPSHOT",
        args_model=None,
        result_model=None,
        notes=None,
    ),
    "RESTORE_PENSION_PORTFOLIO_SNAPSHOT": ToolContract(
        tool_name="RESTORE_PENSION_PORTFOLIO_SNAPSHOT",
        args_model=None,
        result_model=None,
        notes=None,
    ),
    "RESTORE_SYSTEM_SNAPSHOT": ToolContract(
        tool_name="RESTORE_SYSTEM_SNAPSHOT",
        args_model=None,
        result_model=None,
        notes=None,
    ),
}


def get_tool_contract(tool_name: str) -> ToolContract | None:
    if not isinstance(tool_name, str) or not tool_name.strip():
        return None
    c = _CONTRACTS.get(tool_name.strip())
    if c is None:
        return None
    if c.args_model is None and c.result_model is None:
        return None
    return c


def validate_tool_args(tool_name: str, tool_args: Any) -> tuple[bool, str | None]:
    contract = get_tool_contract(tool_name)
    if contract is None or contract.args_model is None:
        return True, None

    args_obj = tool_args if isinstance(tool_args, dict) else {}

    try:
        contract.args_model.model_validate(args_obj)
        return True, None
    except ValidationError as e:
        return False, str(e)[:2000]
    except Exception as e:
        return False, f"Unexpected validation error: {type(e).__name__}: {str(e)[:500]}"


def _parse_tool_result_json(tool_result: Any) -> tuple[dict | None, str | None]:
    if isinstance(tool_result, dict):
        return tool_result, None

    if not isinstance(tool_result, str):
        return None, f"Tool result is not a string: {type(tool_result).__name__}"

    raw = tool_result.strip()
    if not raw:
        return None, "Tool result is empty"

    try:
        parsed = json.loads(raw)
    except Exception as e:
        return (
            None,
            f"Tool result is not valid JSON: {type(e).__name__}: {str(e)[:500]}",
        )

    if not isinstance(parsed, dict):
        return None, f"Tool result JSON is not an object: {type(parsed).__name__}"

    return parsed, None


def validate_tool_result(tool_name: str, tool_result: Any) -> tuple[bool, str | None]:
    contract = get_tool_contract(tool_name)
    if contract is None or contract.result_model is None:
        return True, None

    parsed, err = _parse_tool_result_json(tool_result)
    if err is not None:
        return False, err

    try:
        contract.result_model.model_validate(parsed)
        return True, None
    except ValidationError as e:
        return False, str(e)[:2000]
    except Exception as e:
        return False, f"Unexpected validation error: {type(e).__name__}: {str(e)[:500]}"
