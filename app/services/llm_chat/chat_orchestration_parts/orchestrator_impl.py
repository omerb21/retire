import json
import logging
import inspect
import re
import uuid
import importlib
from datetime import date
from typing import Any, Optional

from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.schemas.llm_chat import ChatMessage, ChatRequest, ChatResponse
from app.services.llm_chat.chat_orchestration_helpers import (
    build_approval_request_ui_action,
    build_forced_document_reply,
    build_pension_portfolio_update_after_transform,
    build_transform_accounts_from_target_plan_payload,
    format_transform_result_for_user,
    get_gross_for_tax_chaining,
    store_pending_approval_request,
    load_pending_approval_request,
    clear_pending_approval_request,
    load_latest_target_pension_plan,
    maybe_clear_pension_portfolio_after_transform,
    run_tax_projection_autochain,
    store_latest_target_pension_plan,
)
from app.services.llm_chat.message_preparation import prepare_messages_with_context
from app.services.llm_chat.message_utils import (
    extract_latest_approval_request,
    extract_user_approval_for_tool_call,
    extract_user_cancel_for_tool_call,
    extract_latest_target_pension_plan_payload,
    extract_target_pension_from_message,
    was_tool_call_previously_approved,
    find_last_user_message,
    is_user_approval_intent_text,
)
from app.services.llm_chat.portfolio_context import build_pension_portfolio_context
from app.services.llm_chat.orchestration_utils import (
    apply_max_exemption_if_requested,
    build_partial_pension_transform_accounts_from_portfolio,
    build_portfolio_wide_after_settlement_severance_transform_accounts_from_portfolio,
    build_portfolio_wide_component_transform_accounts_from_portfolio,
    build_portfolio_wide_education_fund_transform_accounts_from_portfolio,
    build_portfolio_wide_prev_employers_severance_transform_accounts_from_portfolio,
    build_targeted_component_transform_accounts_from_portfolio,
    build_transform_accounts_from_portfolio,
    build_tax_result_system_message_for_chat,
    build_tool_call_message_content,
    build_tool_result_system_message_for_chat,
    compute_default_retirement_date_for_tool_call,
    normalize_retirement_date_if_jan1_placeholder,
    format_tool_output_for_user_stream,
    sanitize_user_visible_text,
    extract_process_termination_choice_overrides,
    extract_process_termination_date_override,
    is_no_termination_request,
    is_tax_documents_request,
    is_document_request,
    is_no_tools_request,
    is_qa_request,
    is_transform_request,
    parse_partial_pension_conversion_request,
    parse_portfolio_wide_after_settlement_severance_conversion_request,
    parse_portfolio_wide_component_conversion_request,
    parse_portfolio_wide_education_fund_conversion_request,
    parse_portfolio_wide_prev_employers_severance_conversion_request,
    parse_targeted_component_conversion_request,
    is_process_termination_request,
    is_pension_commutation_request,
    is_termination_change_request,
    is_max_exemption_request,
    is_net_pension_request,
    is_retirement_cashflow_request,
    is_retirement_comparison_request,
    is_portfolio_breakdown_request,
    is_portfolio_analysis_request,
    is_max_capital_request,
    extract_desired_monthly_income_from_text,
    is_data_awareness_request,
    is_list_all_financial_entities_request,
    infer_desired_income_is_net_explicit,
    is_cashflow_missing_income_followup,
    parse_tool_call_from_reply,
    validate_tool_call_protocol_for_execution,
)
from app.models.client import Client
from app.models import CurrentEmployer, EmployerGrant, GrantType
from .chat_helpers import (
    _digits_only,
    _extract_commutation_account_number,
    _extract_target_monthly_pension,
    _fmt_money,
    _infer_target_is_net,
    _infer_target_is_net_explicit,
    _is_aggregate_account,
    _is_ignore_blocked_text,
    _is_target_plan_adjust_followup,
    _is_target_plan_adjust_request,
    _item_to_dict,
    _user_requested_target_pension_plan,
    _user_wants_full_balance,
)
from .tool_calling import _execute_tool_call, _get_chat_orchestration_facade
from .chat_top_level_helpers import (
    _get_llm_service,
    _load_latest_pension_portfolio_snapshot_models,
)
from app.utils.llm_chat_log import (
    generate_request_id,
    log_llm_event,
    set_current_case_id,
    set_current_request_id,
)
from app.services.llm_chat.numeric_provenance import validate_reply_numeric_provenance
from .non_stream_stream_entrypoint import run_pension_chat_stream
from .orchestrator_impl_parts.steps import (
    _build_chat_response,
    _prepare_orchestration_inputs,
    _run_orchestration,
)

logger = logging.getLogger("app.llm_chat")


def run_pension_chat(request: ChatRequest, db: Session) -> ChatResponse:
    request_id = generate_request_id()
    set_current_request_id(request_id)

    prepared = _prepare_orchestration_inputs(
        request=request,
        db=db,
        request_id=request_id,
        logger=logger,
        log_llm_event_fn=log_llm_event,
    )
    if isinstance(prepared, ChatResponse):
        return prepared

    orch_res = _run_orchestration(
        request=request,
        db=db,
        messages=prepared.messages,
        request_id=request_id,
        original_user_msg=prepared.original_user_msg,
        current_pension_portfolio=prepared.current_pension_portfolio,
        is_qa_mode=prepared.is_qa_mode,
        no_tools_requested=prepared.no_tools_requested,
        is_doc_request=prepared.is_doc_request,
        is_cashflow_request=prepared.is_cashflow_request,
        is_comparison_request=prepared.is_comparison_request,
        is_net_request=prepared.is_net_request,
        is_portfolio_analysis=prepared.is_portfolio_analysis,
        analysis_default_retirement_age=prepared.analysis_default_retirement_age,
        force_max_exemption=prepared.force_max_exemption,
        wants_ignore_blocked=prepared.wants_ignore_blocked,
        explicit_termination=prepared.explicit_termination,
        termination_change=prepared.termination_change,
        termination_already_executed=prepared.termination_already_executed,
        wants_execute_target_plan=prepared.wants_execute_target_plan,
        wants_fixation_execute=prepared.wants_fixation_execute,
        logger=logger,
        computed_data=prepared.computed_data,
        log_llm_event_fn=log_llm_event,
    )
    if isinstance(orch_res, ChatResponse):
        return orch_res
    final_reply = orch_res.final_reply
    forced_user_prefix = orch_res.forced_user_prefix
    qa_summary_required = orch_res.qa_summary_required
    report_open_path = orch_res.report_open_path
    current_step = orch_res.current_step
    max_steps = orch_res.max_steps
    computed_data = prepared.computed_data
    is_portfolio_analysis = prepared.is_portfolio_analysis

    log_llm_event(
        request_id=request_id,
        event_type="final_answer",
        payload=final_reply,
        client_id=request.client_id,
    )

    return _build_chat_response(
        final_reply=final_reply,
        forced_user_prefix=forced_user_prefix,
        is_portfolio_analysis=is_portfolio_analysis,
        qa_summary_required=qa_summary_required,
        report_open_path=report_open_path,
        current_step=current_step,
        max_steps=max_steps,
        computed_data=computed_data,
    )

