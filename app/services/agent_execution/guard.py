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

    if policy_decision is not None and (
        not bool(getattr(policy_decision, "tools_allowed", True))
    ):
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
                "tools_disabled_reason": getattr(
                    request, "tools_disabled_reason", None
                ),
            },
        )

    try:
        from app.services.llm_chat.case_context import get_current_case_id
        from app.services.llm_chat.tool_execution import WRITE_TOOLS

        case_id = get_current_case_id()
        if (
            case_id == "interactive_readonly"
            and (not bool(user_approved))
            and tool_name in set(WRITE_TOOLS or set())
        ):
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


def build_blocked_tool_result(
    *, tool_name: str, error_code: str, message: str, details: dict
) -> object:
    detected_capability_id = "unknown"
    mode = "ACTION"
    try:
        from app.services.llm_chat.capability_router.runtime_context import (
            get_router_decision,
        )
        from app.utils.trace_context import get_current_trace_id

        trace_id = get_current_trace_id()
        router_decision = get_router_decision(trace_id=trace_id)
        if router_decision is not None:
            detected_capability_id = str(
                getattr(router_decision, "capability_id", None)
                or detected_capability_id
            )
            mode = str(getattr(router_decision, "mode", None) or mode)
    except Exception:
        pass

    normalized_error = str(error_code or "").strip() or "UNKNOWN"

    if normalized_error == "CLIENT_REQUIRED":
        return {
            "mode": mode,
            "status": "missing_data",
            "detected_capability_id": detected_capability_id,
            "what_ran": [],
            "missing_fields": ["client_id"],
            "next_step": "provide_missing_fields",
        }

    policy_reason = None
    try:
        reason_map = {
            "TOOLS_NOT_ALLOWED": "qa_mode_no_tools",
            "TOOL_NOT_ALLOWED": "tool_not_in_allowlist",
        }
        policy_reason = reason_map.get(normalized_error)
    except Exception:
        policy_reason = None

    payload = {
        "mode": mode,
        "status": "policy_blocked",
        "detected_capability_id": detected_capability_id,
        "what_ran": [],
        "missing_fields": [],
        "next_step": "adjust_request",
    }
    if isinstance(policy_reason, str) and policy_reason:
        payload["policy_reasons"] = [policy_reason]
    return payload
