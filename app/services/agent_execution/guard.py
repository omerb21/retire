from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.schemas.llm_chat import ChatRequest
from app.services.agent_execution.policy import PolicyDecision
from app.services.intent_classifier import IntentType


@dataclass(frozen=True)
class GuardResult:
    ok: bool
    error_code: str | None
    message: str | None
    details: dict


def run_pre_tool_guard(
    *,
    request: ChatRequest,
    db: Session | None,
    tool_name: str,
    tool_args: dict,
    policy_decision: PolicyDecision | None,
    intent_type: IntentType | None,
    user_approved: bool = False,
) -> GuardResult:
    _ = (tool_args, intent_type)

    tools_enabled = True
    try:
        tools_enabled = bool(getattr(request, "tools_enabled", True))
    except Exception:
        tools_enabled = True

    if policy_decision is not None and (not bool(getattr(policy_decision, "tools_allowed", True))):
        return GuardResult(
            ok=False,
            error_code="TOOLS_NOT_ALLOWED",
            message="Tools are not allowed for this request.",
            details={},
        )

    if not tools_enabled:
        return GuardResult(
            ok=False,
            error_code="TOOLS_NOT_ALLOWED",
            message="Tools are disabled for this request.",
            details={
                "tools_disabled_reason": getattr(request, "tools_disabled_reason", None),
            },
        )

    try:
        from app.services.llm_chat.tool_execution import WRITE_TOOLS
        from app.services.llm_chat.case_context import get_current_case_id

        case_id = get_current_case_id()
        if case_id == "interactive_readonly" and (not bool(user_approved)) and tool_name in set(WRITE_TOOLS or set()):
            return GuardResult(
                ok=False,
                error_code="TOOL_NOT_ALLOWED",
                message="Write tools are not allowed in interactive_readonly without approval.",
                details={"tool_name": tool_name, "case_id": case_id},
            )
    except Exception:
        pass

    if request.client_id is None:
        return GuardResult(
            ok=False,
            error_code="CLIENT_REQUIRED",
            message="Tool execution requires client_id.",
            details={"tool_name": tool_name},
        )

    return GuardResult(ok=True, error_code=None, message=None, details={})


def build_blocked_tool_result(*, tool_name: str, error_code: str, message: str, details: dict) -> str:
    return json.dumps(
        {
            "success": False,
            "error": error_code,
            "message": message,
            "tool_name": tool_name,
            "details": details or {},
        },
        ensure_ascii=False,
    )
