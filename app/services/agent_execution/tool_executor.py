from __future__ import annotations

from sqlalchemy.orm import Session

from app.schemas.llm_chat import ChatRequest
from app.services.agent_execution.guard import build_blocked_tool_result, run_pre_tool_guard
from app.services.agent_execution.policy import PolicyDecision
from app.services.agent_execution.tool_execution_context import (
    get_current_tool_execution_intent_type,
    get_current_tool_execution_policy_decision,
    get_current_tool_execution_request,
    get_current_tool_execution_streaming,
)
from app.services.agent_trace_logger import log_trace_event
from app.services.intent_classifier import IntentType


def execute_with_guard(
    *,
    request: ChatRequest,
    db: Session,
    tool_name: str,
    tool_args: dict,
    streaming: bool,
    policy_decision: PolicyDecision | None,
    intent_type: IntentType | None,
    pension_portfolio=None,
    force_max_exemption: bool = False,
    agent_reply: str | None = None,
    user_approved: bool = False,
    request_id: str | None = None,
) -> str:
    guard_res = run_pre_tool_guard(
        request=request,
        db=db,
        tool_name=tool_name,
        tool_args=tool_args if isinstance(tool_args, dict) else {},
        policy_decision=policy_decision,
        intent_type=intent_type,
        user_approved=user_approved,
    )

    if not guard_res.ok:
        try:
            payload = {
                "tool_name": tool_name,
                "error_code": guard_res.error_code,
                "message": guard_res.message,
                "details": guard_res.details or {},
                "streaming": bool(streaming),
                "intent_type": getattr(intent_type, "value", None) if intent_type is not None else None,
            }
            log_trace_event(event_type="validation_error", payload=payload, client_id=request.client_id)
        except Exception:
            pass

        return build_blocked_tool_result(
            tool_name=tool_name,
            error_code=str(guard_res.error_code or "VALIDATION_ERROR"),
            message=str(guard_res.message or "Blocked by guard."),
            details=guard_res.details or {},
        )

    from app.services.llm_chat.tool_execution import execute_tool_call as _execute_tool_call_impl

    return _execute_tool_call_impl(
        tool_name=tool_name,
        args=tool_args if isinstance(tool_args, dict) else {},
        client_id=int(request.client_id) if request.client_id is not None else 0,
        db=db,
        pension_portfolio=pension_portfolio,
        force_max_exemption=force_max_exemption,
        agent_reply=agent_reply,
        user_approved=user_approved,
    )


def execute_tool_call(
    tool_name: str,
    args: dict,
    client_id: int,
    db: Session,
    pension_portfolio=None,
    force_max_exemption: bool = False,
    agent_reply: str | None = None,
    user_approved: bool = False,
    request_id: str | None = None,
) -> str:
    req = get_current_tool_execution_request()
    policy_decision = get_current_tool_execution_policy_decision()
    intent_type = get_current_tool_execution_intent_type()
    streaming = get_current_tool_execution_streaming()

    if req is None:
        req_for_exec = ChatRequest(messages=[], client_id=client_id)
    else:
        if getattr(req, "client_id", None) is None:
            try:
                req_for_exec = req.model_copy(update={"client_id": client_id}, deep=True)
            except Exception:
                req_for_exec = ChatRequest(messages=list(getattr(req, "messages", []) or []), client_id=client_id)
        else:
            req_for_exec = req

    return execute_with_guard(
        request=req_for_exec,
        db=db,
        tool_name=tool_name,
        tool_args=args if isinstance(args, dict) else {},
        streaming=bool(streaming),
        policy_decision=policy_decision,
        intent_type=intent_type,
        pension_portfolio=pension_portfolio,
        force_max_exemption=force_max_exemption,
        agent_reply=agent_reply,
        user_approved=user_approved,
        request_id=request_id,
    )
