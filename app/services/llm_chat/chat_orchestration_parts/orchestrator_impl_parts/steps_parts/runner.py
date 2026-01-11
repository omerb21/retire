
import json
from dataclasses import dataclass
from typing import Any

from app.schemas.llm_chat import ChatMessage, ChatResponse
from app.services.llm_chat.orchestration_utils import sanitize_user_visible_text


from ..steps.messages_prompt import _build_messages_and_prompt
from ..steps.types import _PreparedOrchestrationInputs

from .types import _OrchestrationResult
from .runner_step_handlers import _handle_no_tool_call_step, _handle_tool_call_step

def _run_orchestration(
    *,
    request,
    db,
    messages,
    request_id: str,
    original_user_msg: str | None,
    current_pension_portfolio,
    is_qa_mode: bool,
    no_tools_requested: bool,
    is_doc_request: bool,
    is_cashflow_request: bool,
    is_comparison_request: bool,
    is_net_request: bool,
    is_portfolio_analysis: bool,
    analysis_default_retirement_age,
    force_max_exemption: bool,
    wants_ignore_blocked: bool,
    explicit_termination: bool,
    termination_change: bool,
    termination_already_executed: bool,
    wants_execute_target_plan: bool,
    wants_fixation_execute: bool,
    logger,
    computed_data,
    log_llm_event_fn,
) -> ChatResponse | _OrchestrationResult:
    from app.models.client import Client
    from app.services.llm_chat.chat_orchestration_helpers import (
        build_approval_request_ui_action,
        build_forced_document_reply,
        build_pension_portfolio_update_after_transform,
        format_transform_result_for_user,
        get_gross_for_tax_chaining,
        load_pending_approval_request,
        run_tax_projection_autochain,
        store_latest_target_pension_plan,
        store_pending_approval_request,
        maybe_clear_pension_portfolio_after_transform,
    )
    from app.services.llm_chat.message_utils import (
        extract_latest_approval_request,
        extract_user_approval_for_tool_call,
        extract_user_cancel_for_tool_call,
        extract_target_pension_from_message,
        find_last_user_message,
        is_user_approval_intent_text,
        was_tool_call_previously_approved,
    )
    from app.services.llm_chat.numeric_provenance import validate_reply_numeric_provenance
    from app.services.llm_chat.orchestration_utils import (
        apply_max_exemption_if_requested,
        build_tax_result_system_message_for_chat,
        build_tool_call_message_content,
        build_tool_result_system_message_for_chat,
        compute_default_retirement_date_for_tool_call,
        format_tool_output_for_user_stream,
        is_cashflow_missing_income_followup,
        is_tax_documents_request,
        normalize_retirement_date_if_jan1_placeholder,
        parse_tool_call_from_reply,
        sanitize_user_visible_text,
        validate_tool_call_protocol_for_execution,
    )
    from app.services.llm_chat.chat_orchestration_parts.chat_helpers import (
        _digits_only,
        _extract_commutation_account_number,
        _extract_target_monthly_pension,
        _fmt_money,
        _infer_target_is_net,
        _infer_target_is_net_explicit,
        _is_aggregate_account,
        _user_requested_target_pension_plan,
        _user_wants_full_balance,
    )
    from app.services.llm_chat.chat_orchestration_parts.chat_top_level_helpers import (
        _get_llm_service,
        _load_latest_pension_portfolio_snapshot_models,
    )
    from app.services.llm_chat.chat_orchestration_parts.tool_calling import _execute_tool_call
    from app.services.llm_chat.orchestration_utils import (
        build_partial_pension_transform_accounts_from_portfolio,
        build_portfolio_wide_after_settlement_severance_transform_accounts_from_portfolio,
        build_portfolio_wide_component_transform_accounts_from_portfolio,
        build_portfolio_wide_education_fund_transform_accounts_from_portfolio,
        build_portfolio_wide_prev_employers_severance_transform_accounts_from_portfolio,
        build_targeted_component_transform_accounts_from_portfolio,
        build_transform_accounts_from_portfolio,
        extract_desired_monthly_income_from_text,
        extract_process_termination_choice_overrides,
        extract_process_termination_date_override,
        infer_desired_income_is_net_explicit,
        is_data_awareness_request,
        is_document_request,
        is_list_all_financial_entities_request,
        is_max_capital_request,
        is_max_exemption_request,
        is_net_pension_request,
        is_no_termination_request,
        is_no_tools_request,
        is_pension_commutation_request,
        is_portfolio_analysis_request,
        is_portfolio_breakdown_request,
        is_process_termination_request,
        is_qa_request,
        is_retirement_cashflow_request,
        is_retirement_comparison_request,
        is_termination_change_request,
        is_transform_request,
        parse_partial_pension_conversion_request,
        parse_portfolio_wide_after_settlement_severance_conversion_request,
        parse_portfolio_wide_component_conversion_request,
        parse_portfolio_wide_education_fund_conversion_request,
        parse_portfolio_wide_prev_employers_severance_conversion_request,
        parse_targeted_component_conversion_request,
    )
    from app.models import CurrentEmployer, EmployerGrant, GrantType

    max_steps = 5
    current_step = 0
    final_reply = ""
    forced_user_prefix: str = ""
    qa_summary_required = False
    report_open_path: str | None = None
    forced_fixation_chain_done = False

    while current_step < max_steps:
        logger.info(
            "🔄 Agent Loop Step %d/%d for client %s",
            current_step + 1,
            max_steps,
            request.client_id,
        )

        raw_reply = _get_llm_service().chat(messages, request.client_id)

        lowered = (raw_reply or "").lower()
        has_pass_fail = ("pass" in lowered) or ("fail" in lowered)

        if is_qa_mode and no_tools_requested and not has_pass_fail and "###TOOL_CALL###" not in raw_reply:
            messages.append(
                ChatMessage(
                    role="system",
                    content=(
                        "אזהרה: המשתמש ביקש QA להסבר בלבד וביקש במפורש לא להפעיל כלים. "
                        "אסור לבצע TOOL_CALL. החזר תשובת PASS או FAIL בלבד + 3-6 שורות סיכום קצר."
                    ),
                )
            )
            current_step += 1
            continue

        if qa_summary_required and not has_pass_fail and "###TOOL_CALL###" not in raw_reply:
            messages.append(
                ChatMessage(
                    role="system",
                    content=(
                        "אזהרה: במצב QA חובה לסיים בתשובת PASS/FAIL וסיכום קצר. "
                        "החזר כעת תשובת PASS או FAIL בלבד + 3-6 שורות סיכום + open_path של הדוח."
                    ),
                )
            )
            current_step += 1
            continue

        (
            handled_tool_call,
            should_break,
            immediate_response,
            original_user_msg,
            current_pension_portfolio,
            final_reply,
            forced_user_prefix,
            qa_summary_required,
            report_open_path,
            forced_fixation_chain_done,
            current_step,
        ) = _handle_tool_call_step(
            request=request,
            db=db,
            request_id=request_id,
            logger=logger,
            log_llm_event_fn=log_llm_event_fn,
            raw_reply=raw_reply,
            original_user_msg=original_user_msg,
            messages=messages,
            current_pension_portfolio=current_pension_portfolio,
            is_qa_mode=is_qa_mode,
            no_tools_requested=no_tools_requested,
            is_doc_request=is_doc_request,
            is_cashflow_request=is_cashflow_request,
            is_comparison_request=is_comparison_request,
            is_net_request=is_net_request,
            is_portfolio_analysis=is_portfolio_analysis,
            analysis_default_retirement_age=analysis_default_retirement_age,
            force_max_exemption=force_max_exemption,
            wants_ignore_blocked=wants_ignore_blocked,
            explicit_termination=explicit_termination,
            termination_change=termination_change,
            termination_already_executed=termination_already_executed,
            wants_execute_target_plan=wants_execute_target_plan,
            wants_fixation_execute=wants_fixation_execute,
            final_reply=final_reply,
            forced_user_prefix=forced_user_prefix,
            qa_summary_required=qa_summary_required,
            report_open_path=report_open_path,
            forced_fixation_chain_done=forced_fixation_chain_done,
            current_step=current_step,
            computed_data=computed_data,
        )

        if immediate_response is not None:
            return immediate_response
        if should_break:
            break
        if handled_tool_call:
            continue

        should_continue, did_break, final_reply, current_step = _handle_no_tool_call_step(
            request=request,
            db=db,
            request_id=request_id,
            logger=logger,
            log_llm_event_fn=log_llm_event_fn,
            raw_reply=raw_reply,
            original_user_msg=original_user_msg,
            messages=messages,
            is_qa_mode=is_qa_mode,
            no_tools_requested=no_tools_requested,
            is_doc_request=is_doc_request,
            is_cashflow_request=is_cashflow_request,
            is_comparison_request=is_comparison_request,
            is_net_request=is_net_request,
            forced_user_prefix=forced_user_prefix,
            final_reply=final_reply,
            current_step=current_step,
        )
        if should_continue:
            continue
        if did_break:
            break

    return _OrchestrationResult(
        final_reply=final_reply,
        forced_user_prefix=forced_user_prefix,
        qa_summary_required=qa_summary_required,
        report_open_path=report_open_path,
        current_step=current_step,
        max_steps=max_steps,
    )
