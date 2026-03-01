from __future__ import annotations

"""Stage D discovery

STAGE_D_GUARD_ENTRYPOINT = "can_execute_tool"
STAGE_D_GUARD_CALLERS = [
    "app.services.llm_chat.chat_stream_orchestration_parts.orchestrator_impl_parts.stream_loop_user_approved_json_exec",
]
STAGE_D_GUARD_RETURN_TYPE = "bool"
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any


DEFAULT_GUARD_BLOCK_CODE = "GUARD_BLOCKED"
DEFAULT_APPROVAL_REQUEST_ID = "APPROVAL_REQUIRED"


class GuardOutcome(str, Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    PENDING = "PENDING"


@dataclass(frozen=True)
class GuardResult:
    outcome: GuardOutcome
    error_code: str | None = None
    approval_request_id: str | None = None
    details: dict[str, Any] | None = None


def can_execute_tool(
    *,
    tool_name: str,
    request_kind: str | None,
    has_pending_approval: bool,
    user_intent: str | None,
) -> bool:
    if not isinstance(tool_name, str) or not tool_name.strip():
        return False

    tool = tool_name.strip().upper()
    intent = (user_intent or "").strip().lower()
    kind = (request_kind or "").strip().lower() or None

    if tool == "BUILD_TARGET_PENSION_PLAN":
        return kind in {"build_target_plan", "target_plan", "build"}

    if tool == "TRANSFORM_FUNDS_TO_ASSETS":
        if intent not in {"execute", "approve"}:
            return False
        return bool(has_pending_approval)

    if tool == "EXECUTE_RETIREMENT_SCENARIO":
        if intent not in {"execute", "approve"}:
            return False
        return bool(has_pending_approval)

    return bool(has_pending_approval)


def evaluate_tool_execution_guard_v2(
    *,
    tool_name: str,
    request_kind: str | None,
    has_pending_approval: bool,
    user_intent: str | None,
) -> GuardResult:
    allowed = can_execute_tool(
        tool_name=tool_name,
        request_kind=request_kind,
        has_pending_approval=has_pending_approval,
        user_intent=user_intent,
    )
    if allowed:
        return GuardResult(outcome=GuardOutcome.ALLOW)

    return GuardResult(
        outcome=GuardOutcome.BLOCK,
        error_code=DEFAULT_GUARD_BLOCK_CODE,
    )
