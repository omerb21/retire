from typing import Any

from app.schemas.llm_chat import ChatMessage, ChatRequest
from app.services.llm_chat.orchestration_utils import (
    apply_max_exemption_if_requested,
    build_tool_call_message_content,
    parse_tool_call_from_reply,
)
from app.utils.llm_chat_log import log_llm_event

from ..chat_helpers import _user_requested_target_pension_plan
from .stream_loop_build_target_pension_plan_guardrail import _maybe_apply_build_target_pension_plan_guardrail
from .stream_loop_cashflow_retirement_date_normalization import _maybe_normalize_cashflow_retirement_date
from .stream_loop_document_request_allowed_tools_guardrail import _maybe_guardrail_document_request_allowed_tools
from .stream_loop_pre_tool_execution_guardrails import _maybe_apply_pre_tool_execution_guardrails
from .stream_loop_retirement_scenarios_portfolio_analysis import _maybe_prepare_retirement_scenarios_args_for_portfolio_analysis
from .stream_loop_transform_funds_to_assets_guardrails import _maybe_guardrail_transform_funds_to_assets
from .stream_loop_commutation_approval import _stream_maybe_request_commutation_approval


def _stream_prepare_tool_call_and_maybe_request_commutation_approval(
    *,
    full_response: str,
    request: ChatRequest,
    db,
    req_id: str,
    history_messages: list[ChatMessage],
    original_user_msg: str,
    is_portfolio_analysis: bool,
    analysis_default_retirement_age: int | None,
    no_tools_requested: bool,
    is_qa_mode: bool,
    is_doc_request: bool,
    is_tax_doc_request: bool,
    wants_ignore_blocked: bool,
    explicit_termination: bool,
    termination_already_executed: bool,
    termination_change: bool,
    current_pension_portfolio,
    wants_capital_transform: bool,
    force_max_exemption_val: bool,
) -> tuple[bool, bool, bool, str | None, Any, Any]:
    parsed = parse_tool_call_from_reply(full_response)
    if parsed is None:
        return False, True, False, None, None, current_pension_portfolio

    text_part, tool_data = parsed
    tool_name = tool_data.get("name")
    tool_args = tool_data.get("arguments", {})

    tool_args = _maybe_prepare_retirement_scenarios_args_for_portfolio_analysis(
        tool_name=tool_name,
        tool_args=tool_args,
        is_portfolio_analysis=is_portfolio_analysis,
        analysis_default_retirement_age=analysis_default_retirement_age,
    )

    if (
        _user_requested_target_pension_plan(original_user_msg)
        and tool_name == "RUN_RETIREMENT_CASHFLOW_ANALYSIS"
    ):
        history_messages.append(
            ChatMessage(
                role="system",
                content=(
                    "אזהרה: המשתמש ביקש לבנות תכנית יעד קצבה (מתווה להשגת יעד חודשי). "
                    "אסור להפעיל RUN_RETIREMENT_CASHFLOW_ANALYSIS בהקשר זה. "
                    "כעת אל תחזיר TOOL_CALL. במקום זאת החזר TOOL_CALL ל-BUILD_TARGET_PENSION_PLAN בלבד "
                    "עם target_monthly_pension כפי שמופיע בבקשת המשתמש."
                ),
            )
        )
        return True, False, False, tool_name, tool_args, current_pension_portfolio

    tool_args, should_continue = _maybe_apply_build_target_pension_plan_guardrail(
        tool_name=tool_name,
        tool_args=tool_args,
        original_user_msg=original_user_msg,
        history_messages=history_messages,
    )
    if should_continue:
        return True, False, False, tool_name, tool_args, current_pension_portfolio

    if tool_name == "PROCESS_TERMINATION" and wants_ignore_blocked:
        history_messages.append(
            ChatMessage(
                role="system",
                content=(
                    "אזהרה: המשתמש ביקש במפורש להתעלם מיתרות חסומות/עזיבת עבודה ולהמשיך ללא טיפול בעזיבת עבודה. "
                    "אסור לבצע עזיבת עבודה. כעת המשך ללא TOOL_CALL ובחר כלי אחר שמתאים לבקשה."
                ),
            )
        )
        return True, False, False, tool_name, tool_args, current_pension_portfolio

    if tool_name == "PROCESS_TERMINATION" and (not explicit_termination):
        allow_change_after_execution = bool(termination_already_executed and termination_change)
        if not allow_change_after_execution:
            history_messages.append(
                ChatMessage(
                    role="system",
                    content=(
                        "אזהרה: אסור לבצע עזיבת עבודה ללא בקשה מפורשת לביצוע עזיבת עבודה/פיצויים. "
                        "כעת המשך ללא TOOL_CALL."
                    ),
                )
            )
            return True, False, False, tool_name, tool_args, current_pension_portfolio

    (
        current_pension_portfolio,
        tool_args,
        should_continue,
    ) = _maybe_guardrail_transform_funds_to_assets(
        tool_name=tool_name,
        wants_ignore_blocked=wants_ignore_blocked,
        is_doc_request=is_doc_request,
        is_qa_mode=is_qa_mode,
        original_user_msg=original_user_msg,
        current_pension_portfolio=current_pension_portfolio,
        request=request,
        db=db,
        tool_args=tool_args,
        wants_capital_transform=wants_capital_transform,
        history_messages=history_messages,
    )
    if should_continue:
        return True, False, False, tool_name, tool_args, current_pension_portfolio

    should_continue = _maybe_guardrail_document_request_allowed_tools(
        is_doc_request=is_doc_request,
        is_qa_mode=is_qa_mode,
        is_tax_doc_request=is_tax_doc_request,
        current_pension_portfolio=current_pension_portfolio,
        tool_name=tool_name,
        history_messages=history_messages,
    )
    if should_continue:
        return True, False, False, tool_name, tool_args, current_pension_portfolio

    should_continue = _maybe_apply_pre_tool_execution_guardrails(
        no_tools_requested=no_tools_requested,
        is_qa_mode=is_qa_mode,
        tool_name=tool_name,
        full_response=full_response,
        history_messages=history_messages,
    )
    if should_continue:
        return True, False, False, tool_name, tool_args, current_pension_portfolio

    log_llm_event(
        request_id=req_id,
        event_type="tool_call",
        payload={"name": tool_name, "arguments": tool_args},
        client_id=request.client_id,
        extra={"endpoint": "stream"},
    )

    apply_max_exemption_if_requested(
        tool_name=tool_name,
        tool_args=tool_args,
        force_max_exemption=force_max_exemption_val,
    )

    _maybe_normalize_cashflow_retirement_date(
        tool_name=tool_name,
        tool_args=tool_args,
        request=request,
        db=db,
        original_user_msg=original_user_msg,
    )

    if text_part:
        history_messages.append(ChatMessage(role="assistant", content=text_part))

    tool_msg_content = build_tool_call_message_content(tool_data, ensure_ascii=False)
    history_messages.append(ChatMessage(role="assistant", content=tool_msg_content))

    should_return = yield from _stream_maybe_request_commutation_approval(
        tool_name=tool_name,
        tool_args=tool_args,
        request=request,
        db=db,
    )
    if should_return:
        return False, False, True, tool_name, tool_args, current_pension_portfolio

    return False, False, False, tool_name, tool_args, current_pension_portfolio
