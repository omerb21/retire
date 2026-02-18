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
}


def get_tool_contract(tool_name: str) -> ToolContract | None:
    if not isinstance(tool_name, str) or not tool_name.strip():
        return None
    return _CONTRACTS.get(tool_name.strip())


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
        return None, f"Tool result is not valid JSON: {type(e).__name__}: {str(e)[:500]}"

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
