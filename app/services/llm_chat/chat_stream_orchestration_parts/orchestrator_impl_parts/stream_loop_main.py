import json
import logging
import inspect
import importlib
import re
import uuid
import time
import threading
import queue
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta, date
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.schemas.llm_chat import ChatMessage, ChatRequest
from app.services.llm_chat.chat_orchestration_helpers import (
    build_forced_document_reply,
    build_pension_portfolio_update_after_commutation,
    build_pension_portfolio_update_after_transform,
    build_transform_accounts_from_target_plan_payload,
    format_transform_result_for_user,
    get_gross_for_tax_chaining,
    build_approval_request_ui_action,
    load_pending_approval_request,
    load_undo_snapshot,
    clear_pending_approval_request,
    store_pending_approval_request,
    store_pending_plan_target_marker,
    load_latest_target_pension_plan,
    load_latest_target_pension_plan_data,
    run_tax_projection_autochain,
    store_latest_target_pension_plan,
    store_latest_target_pension_plan_data,
    store_latest_retirement_cashflow_analysis,
    load_latest_retirement_cashflow_analysis,
)
from app.services.llm_chat.pending_approvals import (
    compute_args_hash,
    load_pending_approval_payload_if_match_and_args_hash,
    load_pending_approval_ui_action_if_match,
)
from app.services.llm_chat.message_preparation import prepare_messages_with_context
from app.services.llm_chat.message_utils import (
    extract_user_approval_for_tool_call,
    extract_user_cancel_for_tool_call,
    extract_latest_approval_request,
    get_tool_call_approval_signature,
    extract_latest_target_pension_plan_payload,
    extract_target_pension_from_message,
    find_last_user_message,
    is_user_approval_intent_text,
    is_undo_intent_text,
)
from app.services.llm_chat.intent_classifier import (
    ChatIntent,
    detect_intent,
    get_stream_base_system_prompt,
    get_stream_system_prompt_for_intent,
    report_requires_qa_line,
)
from app.guards.advisor_behavior_guard import enforce_behavioral_limits
from app.guards.tool_intent_guard import (
    is_conceptual_no_execute_request,
    sanitize_words_only_conceptual,
    sanitize_words_only_output,
)
from app.guards.advice_domain import AdviceDomain
from app.guards.advice_domain_resolver import resolve_advice_domain
from app.guards.orchestration_plan import OrchestrationPlan
from app.guards.orchestration_plan_resolver import resolve_orchestration_plan
from app.services.llm_chat.portfolio_context import build_pension_portfolio_context
from app.services.llm_chat.orchestration_utils import (
    apply_max_exemption_if_requested,
    build_tool_call_message_content,
    build_transform_accounts_from_portfolio,
    build_portfolio_wide_component_transform_accounts_from_portfolio,
    build_portfolio_wide_education_fund_transform_accounts_from_portfolio,
    build_portfolio_wide_prev_employers_severance_transform_accounts_from_portfolio,
    build_targeted_component_transform_accounts_from_portfolio,
    build_partial_pension_transform_accounts_from_portfolio,
    build_transform_accounts_from_portfolio,
    build_tax_result_system_message_for_stream,
    build_tool_call_message_content,
    build_tool_result_system_message_for_stream,
    extract_explicit_gender_and_age_from_text,
    extract_explicit_retirement_date_from_text,
    extract_process_termination_choice_overrides,
    extract_process_termination_date_override,
    format_tool_output_for_user_stream,
    get_tool_display_name_hebrew,
    is_document_request,
    is_portfolio_breakdown_request,
    is_tax_documents_request,
    is_max_exemption_request,
    is_net_pension_request,
    is_no_termination_request,
    is_no_tools_request,
    is_portfolio_analysis_request,
    is_process_termination_request,
    is_pension_commutation_request,
    is_qa_request,
    is_retirement_cashflow_request,
    is_retirement_comparison_request,
    is_termination_change_request,
    is_transform_request,
    is_max_capital_request,
    extract_desired_monthly_income_from_text,
    is_data_awareness_request,
    is_list_all_financial_entities_request,
    infer_desired_income_is_net_explicit,
    is_cashflow_missing_income_followup,
    parse_partial_pension_conversion_request,
    parse_portfolio_wide_prev_employers_severance_conversion_request,
    parse_portfolio_wide_education_fund_conversion_request,
    parse_portfolio_wide_component_conversion_request,
    parse_portfolio_wide_after_settlement_severance_conversion_request,
    parse_targeted_component_conversion_request,
    resolve_target_retirement_age,
    normalize_retirement_date_if_jan1_placeholder,
    parse_tool_call_from_reply,
    sanitize_user_visible_text,
    compute_default_retirement_date_for_tool_call,
    compute_retirement_date_from_birth_date,
    extract_explicit_retirement_age_from_text,
    extract_relative_retirement_years_from_text,
)
from app.services.llm_chat.numeric_provenance import validate_reply_numeric_provenance
from app.services.pension_portfolio.snapshot_loader import (
    load_current_effective_state,
    load_latest_pension_portfolio_snapshot_models,
)
from app.services.state.effective_client_state_loader import load_effective_client_state
from app.services.llm_chat.execution_only_guard import (
    is_execution_only,
    get_execution_only_system_prompt,
    validate_execution_only_output,
    execution_only_blocked,
)
from app.services.llm_chat.prompts_stream_retirement_kb import get_stream_professional_system_prompt
from app.services.llm_chat.execution_only_rewriter import build_exec_only_rewrite_prompt
from app.services.llm_chat.execution_only_fallback import build_execution_only_fallback
from app.models.client import Client
from app.models.scenario import Scenario
from app.models import CurrentEmployer, EmployerGrant, GrantType
from app.utils.knowledge_loader import get_retirement_kb_for_stream
from app.utils.llm_chat_log import (
    generate_request_id,
    log_llm_event,
    set_current_case_id,
    set_current_request_id,
)
from app.services.llm_agent_tools_service import AgentToolsService
from app.services.llm_chat.orchestration_utils_parts.existing_income_offset import (
    compute_existing_income_offset_monthly,
)
from ..chat_helpers import (
    _digits_only,
    _extract_commutation_account_number,
    _extract_target_monthly_pension,
    _first_name,
    _fmt_money,
    _format_system_results_from_cashflow,
    _infer_target_is_net,
    _infer_target_is_net_explicit,
    _is_ignore_blocked_text,
    _is_system_inventory_request,
    _is_system_results_request,
    _is_target_plan_adjust_followup,
    _is_target_plan_adjust_request,
    _item_to_dict,
    _last_assistant_message_text,
    _user_requested_target_pension_plan,
    _user_wants_full_balance,
)
from ..stream_top_level_helpers import (
    _build_transform_accounts_from_target_plan_payload,
    _get_llm_service,
    _get_retry_settings,
    _get_stream_orchestration_facade,
    _load_latest_pension_portfolio_snapshot_models,
    _store_pending_approval_request,
)
from ..stream_tool_execution import _execute_tool_call
from ..stream_more_nested_helpers import _format_system_inventory_snapshot
from ..stream_formatters import _format_data_awareness_snapshot, _format_list_all_entities
from ..stream_streaming_helpers import _stream_execute_tool_no_approval, _stream_request_approval
from ..stream_llm_collectors import _collect_llm_response_with_retry
from ..stream_commutation_generators import (
    generate_commutation_need_account,
    generate_commutation_need_amount_existing,
    generate_commutation_need_amount,
    generate_commutation_missing,
)
from ..stream_system_prompt_generators import (
    generate_adjust_reply,
    generate_system_results,
    generate_system_inventory,
    generate_data_awareness,
    generate_list_all_entities,
    generate_target_plan,
    generate_cashflow,
)
from ..stream_portfolio_analysis_generators import (
    generate_breakdown,
    generate_portfolio_analysis,
)
from ..stream_approval_generators import (
    generate_forced_approval,
    generate_execute_target_after_termination,
    generate_approval_exec,
)
from .stream_loop_explicit_transform import _stream_handle_explicit_transform
from .stream_loop_commutation_deterministic import _maybe_handle_commutation_deterministic
from .stream_loop_commutation_approval import _stream_maybe_request_commutation_approval
from .stream_loop_cashflow_retirement_date_normalization import _maybe_normalize_cashflow_retirement_date
from .stream_loop_retirement_scenarios_portfolio_analysis import _maybe_prepare_retirement_scenarios_args_for_portfolio_analysis
from .stream_loop_forced_fixation_chain import _stream_run_forced_fixation_chain_if_needed
from .stream_loop_transform_tool_args_accounts_override import _maybe_override_transform_tool_args_accounts
from .stream_loop_missing_required_tools_guardrail import _maybe_append_missing_required_tools_guardrail
from .stream_loop_tax_autochain_output import _stream_maybe_emit_tax_autochain_result
from .stream_loop_forced_document_reply import _stream_maybe_emit_forced_document_reply
from .stream_loop_tax_force_chaining import _maybe_run_tax_force_chaining
from .stream_loop_numeric_provenance_guardrail import _compute_final_out_with_numeric_provenance_guardrail
from .stream_loop_numeric_provenance_allowed_sources import _build_allowed_sources_for_numeric_provenance
from .stream_loop_build_target_pension_plan_guardrail import _maybe_apply_build_target_pension_plan_guardrail
from .stream_loop_mandatory_fixation_chain import _stream_maybe_run_mandatory_fixation_chain
from .stream_loop_ui_action_approval_short_circuit import _stream_maybe_short_circuit_on_ui_action_approval_request
from .stream_loop_document_request_allowed_tools_guardrail import _maybe_guardrail_document_request_allowed_tools
from .stream_loop_transform_funds_to_assets_guardrails import _maybe_guardrail_transform_funds_to_assets
from .stream_loop_pre_tool_execution_guardrails import _maybe_apply_pre_tool_execution_guardrails
from .stream_loop_post_tool_execution_processing import _stream_handle_post_tool_execution_processing
from .stream_loop_non_tool_response_guardrails import _maybe_apply_non_tool_response_guardrails
from .stream_loop_tool_call_preparation import _stream_prepare_tool_call_and_maybe_request_commutation_approval
from .stream_loop_llm_response_with_retry import _stream_collect_llm_response_with_retry_or_yield_error
from .stream_loop_tool_execution_and_processing import _stream_execute_tool_and_process_result
from .stream_loop_approval_cancel_handling import _maybe_handle_approval_or_cancel_flow
from .stream_loop_max_capital_deterministic import _maybe_handle_max_capital_request
from .stream_loop_system_message_injection import (
    _apply_wants_ignore_blocked_and_portfolio_analysis_messages,
)
from .stream_loop_termination_deterministic import _maybe_handle_termination_deterministic
from .stream_loop_analysis_default_retirement_age import _compute_analysis_default_retirement_age
from .stream_loop_fixation_documents_deterministic import _maybe_handle_fixation_documents_deterministic
from .stream_loop_target_plan_deterministic import _maybe_handle_target_plan_deterministic
from .stream_loop_cashflow_deterministic import _maybe_handle_cashflow_deterministic
from .stream_loop_pre_retirement_plan_resolution import (
    _clear_pending_pre_retirement_plan_resolution,
    _coerce_float_safe,
    _compute_existing_fixed_net_income_monthly,
    _detect_blocked_balances_in_snapshot,
    _load_pending_pre_retirement_plan_resolution,
    _pre_retirement_plan_resolution,
    _store_pending_pre_retirement_plan_resolution,
    _today,
)
from .stream_loop_plan_target_marker import (
    PendingPlanTargetMarker,
    delete_marker,
    extract_target_net_ils,
    load_pending_plan_target_marker_direct,
)
from .stream_loop_pending_plan_target_flow import _maybe_handle_pending_plan_target_flow
from .stream_loop_restore_snapshot_banner import (
    _build_recent_state_banner as _build_recent_state_banner_helper,
    _build_restore_snapshot_banner as _build_restore_snapshot_banner_helper,
    _latest_snapshot_operation_type as _latest_snapshot_operation_type_helper,
    _wrap_with_restore_banner as _wrap_with_restore_banner_helper,
)
from .stream_loop_post_conversion_lock import (
    _build_post_conversion_lock_message as _build_post_conversion_lock_message_helper,
    _build_post_conversion_plan_message as _build_post_conversion_plan_message_helper,
    _is_post_conversion_locked as _is_post_conversion_locked_helper,
    _maybe_handle_post_conversion_lock_early_cutoff,
    _should_show_post_conversion_messages as _should_show_post_conversion_messages_helper,
)
from .stream_loop_transform_next_step_hint import _append_transform_next_step_hint
from .stream_loop_user_approved_json_exec import _maybe_handle_user_approved_json_exec
from .stream_loop_restore_snapshot_approval_request import _maybe_handle_restore_snapshot_approval_request
from .stream_loop_advice_mode import _maybe_handle_advice_mode
from .stream_loop_history_messages_setup import _build_history_messages_for_stream
from .stream_loop_non_tool_finalization import _stream_finalize_non_tool_response
from .stream_loop_generate_preamble import _stream_generate_preamble
from .stream_loop_tool_call_iteration import _stream_handle_tool_call_iteration
from .stream_loop_conceptual_no_execute import _maybe_handle_conceptual_no_execute_hard_stop
from .stream_loop_undo_snapshot_approval_request import _maybe_handle_undo_snapshot_approval_request
from .stream_loop_pre_context_flows import _run_pre_context_flows
from .stream_loop_post_conversion_entry_flow import _run_post_conversion_entry_flow
from .stream_loop_runtime_wrappers import _build_runtime_wrappers
from .stream_loop_early_cutoffs import _maybe_handle_early_cutoffs
from .stream_loop_run_helpers_basic import (
    infer_pending_retirement_fields_for_marker as _infer_pending_retirement_fields_for_marker_impl,
    infer_retirement_age_for_plan_args as _infer_retirement_age_for_plan_args_impl,
    is_tool_error_text as _is_tool_error_text_impl,
    cashflow_missing_target_prompt as _cashflow_missing_target_prompt_impl,
    cashflow_missing_age_gender_prompt as _cashflow_missing_age_gender_prompt_impl,
    cashflow_missing_retirement_date_prompt as _cashflow_missing_retirement_date_prompt_impl,
    has_any_digit as _has_any_digit_impl,
    is_explain_in_words_request as _is_explain_in_words_request_impl,
    is_general_retirement_help_request as _is_general_retirement_help_request_impl,
    is_general_retirement_intro_request as _is_general_retirement_intro_request_impl,
)
from .stream_loop_general_retirement_responses import _maybe_handle_general_retirement_responses
from .stream_loop_plan_phrase_flow import _maybe_handle_plan_phrase_flow
from .stream_loop_pre_retirement_yes_no_flow import _maybe_handle_pre_retirement_plan_resolution_yes_no
from .stream_loop_text_approval_flow import _maybe_handle_text_approval_flow
from .stream_loop_pending_plan_marker_flow import _maybe_handle_pending_plan_target_marker_flow
from .stream_loop_reports_routing import _maybe_route_to_reports_page
from .stream_loop_user_approved_exec_flow import _maybe_handle_user_approved_exec_flow
from .stream_loop_system_results_report_flow import _maybe_handle_system_results_report_request
from .stream_loop_report_intent_ui_shortcut import _maybe_handle_report_intent_ui_shortcut
from .stream_loop_plan_tokens_gate import _compute_plan_tokens_gate
from .stream_loop_system_info_requests import _maybe_handle_system_info_requests
from .stream_loop_requested_cashflow_calc import _maybe_handle_requested_cashflow_calc
from .stream_loop_full_report_no_approval import _maybe_handle_full_report_no_approval
from .stream_loop_tools_and_state_setup import _setup_tools_and_state
from .stream_loop_orchestration_plan_shortcuts import _maybe_handle_orchestration_plan_shortcuts
from .stream_loop_post_conversion_lock_blocks import (
    _maybe_handle_post_conversion_lock_early_block,
    _maybe_handle_post_conversion_lock_late_block,
)
from .stream_loop_deterministic_routing_block import _run_deterministic_routing_block
from .stream_loop_generate_loop import _build_streaming_response_generate_loop
from .stream_loop_tail_flow import _run_stream_loop_tail_flow
from .stream_loop_intents_playbook_loader import _load_stream_intents_playbook_text

logger = logging.getLogger("app.llm_chat")

_NO_TOOLS_DECISION_PHRASES: tuple[str, ...] = (
    "האם",
    "למה",
    "איך",
    "בחר",
    "תעדיף",
    "מעוניין",
    "שאלה אחת",
)

_NO_TOOLS_FIXED_ENDING = "קיבלתי. אפשר להמשיך בהסבר מילולי בלבד על בסיס הנתונים שנשלחו."


def _postprocess_no_tools_user_visible_text(text: str) -> str:
    if not isinstance(text, str):
        return _NO_TOOLS_FIXED_ENDING
    out = text
    out = out.replace("?", " ")
    try:
        out = re.sub(r"\b(?:האם|תרצה|בחר)\b", " ", out)
    except Exception:
        pass
    out = re.sub(r"[\t ]+", " ", out)
    out = re.sub(r"\s+\.\s+", ". ", out)
    out = re.sub(r"\s+\n", "\n", out)
    out = re.sub(r"\n\s+", "\n", out)
    out = re.sub(r"[ \t]{2,}", " ", out)
    if not out.endswith(_NO_TOOLS_FIXED_ENDING):
        out = (out + "\n\n" if out else "") + _NO_TOOLS_FIXED_ENDING
    return out

PC_LLM_MAX_RETRIES = 3
PC_LLM_TIMEOUT_SECONDS = 120.0
PC_LLM_BACKOFF_SECONDS = (0.75, 1.5, 3.0)

def run_pension_chat_stream(request: ChatRequest, db: Session) -> StreamingResponse:
    stream_request_id = generate_request_id()
    set_current_request_id(stream_request_id)

    try:
        object.__setattr__(request, "prompt_variant", "pension_chat_stream_v2")
    except Exception:
        pass

    exec_only_active = is_execution_only(request)

    computed_data = None

    raw_user_msg = find_last_user_message(request.messages)

    original_user_msg = (raw_user_msg or "").strip()

    force_max_exemption = False

    effective_portfolio = request.pension_portfolio
    effective_snapshot_at = request.pension_portfolio_snapshot_at

    # FLOW A: Conceptual-only hard stop must be early, before any deterministic tool/approval paths.
    # Apply ONLY when the user explicitly asked not to execute ("בלי לבצע" / "אל תבצע" etc),
    # to avoid breaking other conceptual-but-structured deterministic flows.
    early_cutoff_response = _maybe_handle_early_cutoffs(
        request=request,
        db=db,
        original_user_msg=original_user_msg,
        maybe_handle_conceptual_no_execute_hard_stop=_maybe_handle_conceptual_no_execute_hard_stop,
        maybe_handle_undo_snapshot_approval_request=_maybe_handle_undo_snapshot_approval_request,
    )
    if early_cutoff_response is not None:
        return early_cutoff_response

    (
        _infer_pending_retirement_fields_for_marker,
        _infer_retirement_age_for_plan_args,
        _is_tool_error_text,
        _cashflow_missing_target_prompt,
        _cashflow_missing_age_gender_prompt,
        _cashflow_missing_retirement_date_prompt,
        _has_any_digit,
        _is_explain_in_words_request,
        _is_general_retirement_help_request,
        _is_general_retirement_intro_request,
    ) = _build_runtime_wrappers(
        original_user_msg=original_user_msg,
        db=db,
        today=_today,
        infer_pending_retirement_fields_for_marker_impl=_infer_pending_retirement_fields_for_marker_impl,
        infer_retirement_age_for_plan_args_impl=_infer_retirement_age_for_plan_args_impl,
        is_tool_error_text_impl=_is_tool_error_text_impl,
        cashflow_missing_target_prompt_impl=_cashflow_missing_target_prompt_impl,
        cashflow_missing_age_gender_prompt_impl=_cashflow_missing_age_gender_prompt_impl,
        cashflow_missing_retirement_date_prompt_impl=_cashflow_missing_retirement_date_prompt_impl,
        has_any_digit_impl=_has_any_digit_impl,
        is_explain_in_words_request_impl=_is_explain_in_words_request_impl,
        is_general_retirement_help_request_impl=_is_general_retirement_help_request_impl,
        is_general_retirement_intro_request_impl=_is_general_retirement_intro_request_impl,
    )

    pre_context_response, plan_phrase_detected, messages, computed_data = _run_pre_context_flows(
        request=request,
        db=db,
        stream_request_id=stream_request_id,
        original_user_msg=original_user_msg,
        ClientModel=Client,
        ScenarioModel=Scenario,
        extract_latest_target_pension_plan_payload=extract_latest_target_pension_plan_payload,
        load_latest_target_pension_plan_data=load_latest_target_pension_plan_data,
        load_latest_target_pension_plan=load_latest_target_pension_plan,
        maybe_handle_general_retirement_responses=_maybe_handle_general_retirement_responses,
        is_general_retirement_help_request=_is_general_retirement_help_request,
        is_general_retirement_intro_request=_is_general_retirement_intro_request,
        is_explain_in_words_request=_is_explain_in_words_request,
        extract_target_net_ils=extract_target_net_ils,
        load_effective_client_state=load_effective_client_state,
        sanitize_user_visible_text=sanitize_user_visible_text,
        load_latest_pension_portfolio_snapshot_models=_load_latest_pension_portfolio_snapshot_models,
        infer_retirement_age_for_plan_args=_infer_retirement_age_for_plan_args,
        pre_retirement_plan_resolution=_pre_retirement_plan_resolution,
        execute_tool_call=_execute_tool_call,
        store_latest_target_pension_plan_data=store_latest_target_pension_plan_data,
        store_latest_target_pension_plan=store_latest_target_pension_plan,
        get_tool_display_name_hebrew=get_tool_display_name_hebrew,
        format_tool_output_for_user_stream=format_tool_output_for_user_stream,
        infer_pending_retirement_fields_for_marker=_infer_pending_retirement_fields_for_marker,
        store_pending_plan_target_marker=store_pending_plan_target_marker,
        maybe_handle_plan_phrase_flow=_maybe_handle_plan_phrase_flow,
        maybe_handle_pre_retirement_plan_resolution_yes_no=_maybe_handle_pre_retirement_plan_resolution_yes_no,
        load_pending_pre_retirement_plan_resolution=_load_pending_pre_retirement_plan_resolution,
        clear_pending_pre_retirement_plan_resolution=_clear_pending_pre_retirement_plan_resolution,
        coerce_float_safe=_coerce_float_safe,
        compute_existing_income_offset_monthly=compute_existing_income_offset_monthly,
        build_transform_accounts_from_portfolio=build_transform_accounts_from_portfolio,
        store_pending_approval_request=store_pending_approval_request,
        build_approval_request_ui_action=build_approval_request_ui_action,
        maybe_handle_text_approval_flow=_maybe_handle_text_approval_flow,
        clear_pending_approval_request=clear_pending_approval_request,
        load_pending_plan_target_marker_direct=load_pending_plan_target_marker_direct,
        delete_marker=delete_marker,
        maybe_handle_pending_plan_target_marker_flow=_maybe_handle_pending_plan_target_marker_flow,
        prepare_messages_with_context=prepare_messages_with_context,
        maybe_route_to_reports_page=_maybe_route_to_reports_page,
        maybe_handle_user_approved_json_exec=_maybe_handle_user_approved_json_exec,
    )
    if pre_context_response is not None:
        return pre_context_response

    (
        post_conversion_entry_response,
        effective_client_state,
        _is_post_conversion_locked,
        _should_show_post_conversion_messages,
        _build_post_conversion_lock_message,
        _build_post_conversion_plan_message,
    ) = _run_post_conversion_entry_flow(
        request=request,
        db=db,
        logger=logger,
        stream_request_id=stream_request_id,
        original_user_msg=original_user_msg,
        messages=messages,
        computed_data=computed_data,
        load_effective_client_state=load_effective_client_state,
        is_post_conversion_locked_helper=_is_post_conversion_locked_helper,
        should_show_post_conversion_messages_helper=_should_show_post_conversion_messages_helper,
        build_post_conversion_lock_message_helper=_build_post_conversion_lock_message_helper,
        build_post_conversion_plan_message_helper=_build_post_conversion_plan_message_helper,
        maybe_handle_restore_snapshot_approval_request=_maybe_handle_restore_snapshot_approval_request,
        store_pending_approval_request=store_pending_approval_request,
        is_no_tools_request=is_no_tools_request,
        maybe_handle_post_conversion_lock_early_cutoff=_maybe_handle_post_conversion_lock_early_cutoff,
        load_pending_approval_ui_action_if_match=load_pending_approval_ui_action_if_match,
        is_transform_request=is_transform_request,
        maybe_handle_user_approved_exec_flow=_maybe_handle_user_approved_exec_flow,
        extract_user_approval_for_tool_call=extract_user_approval_for_tool_call,
        load_pending_approval_request=load_pending_approval_request,
        clear_pending_approval_request=clear_pending_approval_request,
        load_latest_pension_portfolio_snapshot_models=_load_latest_pension_portfolio_snapshot_models,
        execute_tool_call=_execute_tool_call,
        get_tool_display_name_hebrew=get_tool_display_name_hebrew,
        format_tool_output_for_user_stream=format_tool_output_for_user_stream,
        sanitize_user_visible_text=sanitize_user_visible_text,
        append_transform_next_step_hint=_append_transform_next_step_hint,
        coerce_float_safe=_coerce_float_safe,
        compute_existing_income_offset_monthly=compute_existing_income_offset_monthly,
        store_latest_target_pension_plan_data=store_latest_target_pension_plan_data,
        store_latest_target_pension_plan=store_latest_target_pension_plan,
    )
    if post_conversion_entry_response is not None:
        return post_conversion_entry_response

    advice_response, resolved_intent, advice_mode, advice_domain, advice_compensation_mode = _maybe_handle_advice_mode(
        exec_only_active=bool(exec_only_active),
        original_user_msg=original_user_msg,
        computed_data=computed_data,
        extract_target_net_ils=extract_target_net_ils,
    )
    if advice_response is not None:
        return advice_response

    (
        tools_enabled_reason,
        tools_disabled_reason,
        tools_enabled,
        ui_action_short_circuit_allowed,
        resolved_intent,
        effective_portfolio,
        effective_snapshot_at,
        effective_state,
        _build_restore_snapshot_banner,
        _latest_snapshot_operation_type,
        _wrap_with_restore_banner,
        _build_recent_state_banner,
    ) = _setup_tools_and_state(
        request=request,
        db=db,
        stream_request_id=stream_request_id,
        original_user_msg=original_user_msg,
        resolved_intent=resolved_intent,
        advice_compensation_mode=bool(advice_compensation_mode),
        log_llm_event=log_llm_event,
        logger=logger,
        load_current_effective_state=load_current_effective_state,
        load_latest_pension_portfolio_snapshot_models=_load_latest_pension_portfolio_snapshot_models,
        build_restore_snapshot_banner_helper=_build_restore_snapshot_banner_helper,
        latest_snapshot_operation_type_helper=_latest_snapshot_operation_type_helper,
        wrap_with_restore_banner_helper=_wrap_with_restore_banner_helper,
        build_recent_state_banner_helper=_build_recent_state_banner_helper,
        ChatIntentClass=ChatIntent,
    )

    (
        target_net_for_plan,
        lowered_user_msg,
        is_plan_request_tokens,
        inferred_ret_age_for_plan_gate,
        has_target_plan_keywords,
        wants_execute_target_plan_text,
        no_tools_requested_local,
        commutation_intent_local,
        explicit_transform_local,
        is_qa_mode_local,
        max_capital_requested_local,
    ) = _compute_plan_tokens_gate(
        request=request,
        db=db,
        original_user_msg=original_user_msg,
        resolved_intent=resolved_intent,
        extract_target_net_ils=extract_target_net_ils,
        resolve_target_retirement_age=resolve_target_retirement_age,
        today=_today,
        ClientModel=Client,
        ChatIntentClass=ChatIntent,
        is_no_tools_request=is_no_tools_request,
        is_pension_commutation_request=is_pension_commutation_request,
        is_transform_request=is_transform_request,
        is_qa_request=is_qa_request,
        is_max_capital_request=is_max_capital_request,
    )

    pending_plan_target_response = _maybe_handle_pending_plan_target_flow(
        request=request,
        db=db,
        stream_request_id=stream_request_id,
        computed_data=computed_data,
        original_user_msg=original_user_msg,
        resolved_intent=resolved_intent,
        tools_enabled=bool(tools_enabled),
        effective_portfolio=effective_portfolio,
        target_net_for_plan=target_net_for_plan,
        lowered_user_msg=lowered_user_msg,
        is_plan_request_tokens=bool(is_plan_request_tokens),
        inferred_ret_age_for_plan_gate=inferred_ret_age_for_plan_gate,
        wants_execute_target_plan_text=bool(wants_execute_target_plan_text),
        commutation_intent_local=bool(commutation_intent_local),
        explicit_transform_local=bool(explicit_transform_local),
        max_capital_requested_local=bool(max_capital_requested_local),
        no_tools_requested_local=bool(no_tools_requested_local),
        is_qa_mode_local=bool(is_qa_mode_local),
        has_target_plan_keywords=bool(has_target_plan_keywords),
        is_post_conversion_locked=_is_post_conversion_locked,
        infer_pending_retirement_fields_for_marker=_infer_pending_retirement_fields_for_marker,
        infer_retirement_age_for_plan_args=_infer_retirement_age_for_plan_args,
        build_recent_state_banner=_build_recent_state_banner,
        load_latest_pension_portfolio_snapshot_models=_load_latest_pension_portfolio_snapshot_models,
        pre_retirement_plan_resolution=_pre_retirement_plan_resolution,
        execute_tool_call=_execute_tool_call,
        store_latest_target_pension_plan_data=store_latest_target_pension_plan_data,
        store_latest_target_pension_plan=store_latest_target_pension_plan,
        format_tool_output_for_user_stream=format_tool_output_for_user_stream,
        sanitize_user_visible_text=sanitize_user_visible_text,
        extract_target_net_ils=extract_target_net_ils,
    )
    if pending_plan_target_response is not None:
        return pending_plan_target_response

    system_results_report_response = _maybe_handle_system_results_report_request(
        request=request,
        db=db,
        stream_request_id=stream_request_id,
        original_user_msg=original_user_msg,
        tools_enabled=bool(tools_enabled),
        effective_portfolio=effective_portfolio,
        latest_snapshot_operation_type=_latest_snapshot_operation_type,
        is_document_request=is_document_request,
        is_tax_documents_request=is_tax_documents_request,
        is_qa_request=is_qa_request,
        is_no_tools_request=is_no_tools_request,
        SessionLocal=SessionLocal,
        execute_tool_call=_execute_tool_call,
    )
    if system_results_report_response is not None:
        return system_results_report_response

    report_intent_shortcut_response = _maybe_handle_report_intent_ui_shortcut(
        request=request,
        tools_enabled=bool(tools_enabled),
        ui_action_short_circuit_allowed=bool(ui_action_short_circuit_allowed),
        resolved_intent=resolved_intent,
    )
    if report_intent_shortcut_response is not None:
        return report_intent_shortcut_response

    plan_advice_domain = advice_domain if advice_mode else None
    plan = resolve_orchestration_plan(
        original_user_msg or "",
        resolved_intent,
        bool(tools_enabled),
        plan_advice_domain,
    )

    plan_shortcut_response = _maybe_handle_orchestration_plan_shortcuts(
        plan=plan,
        request=request,
        db=db,
        stream_request_id=stream_request_id,
        computed_data=computed_data,
        effective_portfolio=effective_portfolio,
        original_user_msg=original_user_msg,
        force_max_exemption=bool(force_max_exemption),
        advice_compensation_mode=bool(advice_compensation_mode),
        build_recent_state_banner=_build_recent_state_banner,
        load_latest_pension_portfolio_snapshot_models=_load_latest_pension_portfolio_snapshot_models,
        generate_cashflow=generate_cashflow,
        execute_tool_call=_execute_tool_call,
        sanitize_user_visible_text=sanitize_user_visible_text,
        format_system_inventory_snapshot=_format_system_inventory_snapshot,
        OrchestrationPlanClass=OrchestrationPlan,
    )
    if plan_shortcut_response is not None:
        return plan_shortcut_response

    system_info_response = _maybe_handle_system_info_requests(
        tools_enabled=bool(tools_enabled),
        request=request,
        db=db,
        computed_data=computed_data,
        effective_portfolio=effective_portfolio,
        effective_snapshot_at=effective_snapshot_at,
        stream_request_id=stream_request_id,
        wrap_with_restore_banner=_wrap_with_restore_banner,
        is_data_awareness_request=is_data_awareness_request,
        generate_data_awareness=generate_data_awareness,
        is_list_all_financial_entities_request=is_list_all_financial_entities_request,
        generate_list_all_entities=generate_list_all_entities,
        is_portfolio_breakdown_request=is_portfolio_breakdown_request,
        generate_breakdown=generate_breakdown,
        is_portfolio_analysis_request=is_portfolio_analysis_request,
        generate_portfolio_analysis=generate_portfolio_analysis,
        is_system_inventory_request=_is_system_inventory_request,
        generate_system_inventory=generate_system_inventory,
        is_system_results_request=_is_system_results_request,
        generate_system_results=generate_system_results,
        original_user_msg=original_user_msg,
    )
    if system_info_response is not None:
        return system_info_response

    return _run_stream_loop_tail_flow(
        request=request,
        db=db,
        messages=messages,
        original_user_msg=original_user_msg,
        resolved_intent=resolved_intent,
        tools_disabled_reason=tools_disabled_reason,
        ui_action_short_circuit_allowed=bool(ui_action_short_circuit_allowed),
        exec_only_active=bool(exec_only_active),
        advice_compensation_mode=bool(advice_compensation_mode),
        plan_phrase_detected=bool(plan_phrase_detected),
        tools_enabled=bool(tools_enabled),
        computed_data=computed_data,
        effective_portfolio=effective_portfolio,
        stream_request_id=stream_request_id,
        logger=logger,
        ChatIntentClass=ChatIntent,
        is_net_pension_request=is_net_pension_request,
        is_document_request=is_document_request,
        is_tax_documents_request=is_tax_documents_request,
        is_qa_request=is_qa_request,
        is_no_tools_request=is_no_tools_request,
        is_max_exemption_request=is_max_exemption_request,
        is_pension_commutation_request=is_pension_commutation_request,
        is_transform_request=is_transform_request,
        is_process_termination_request=is_process_termination_request,
        is_termination_change_request=is_termination_change_request,
        is_retirement_cashflow_request=is_retirement_cashflow_request,
        is_retirement_comparison_request=is_retirement_comparison_request,
        is_portfolio_analysis_request=is_portfolio_analysis_request,
        extract_target_net_ils=extract_target_net_ils,
        is_cashflow_missing_income_followup=is_cashflow_missing_income_followup,
        maybe_handle_requested_cashflow_calc=_maybe_handle_requested_cashflow_calc,
        build_recent_state_banner=_build_recent_state_banner,
        load_latest_pension_portfolio_snapshot_models=_load_latest_pension_portfolio_snapshot_models,
        generate_cashflow=generate_cashflow,
        maybe_handle_full_report_no_approval=_maybe_handle_full_report_no_approval,
        latest_snapshot_operation_type=_latest_snapshot_operation_type,
        stream_execute_tool_no_approval=_stream_execute_tool_no_approval,
        should_show_post_conversion_messages=_should_show_post_conversion_messages,
        maybe_handle_post_conversion_lock_early_block=_maybe_handle_post_conversion_lock_early_block,
        maybe_handle_post_conversion_lock_late_block=_maybe_handle_post_conversion_lock_late_block,
        load_pending_approval_ui_action_if_match=load_pending_approval_ui_action_if_match,
        build_post_conversion_lock_message=_build_post_conversion_lock_message,
        build_post_conversion_plan_message=_build_post_conversion_plan_message,
        run_deterministic_routing_block=_run_deterministic_routing_block,
        maybe_handle_target_plan_deterministic=_maybe_handle_target_plan_deterministic,
        extract_commutation_account_number=_extract_commutation_account_number,
        generate_commutation_need_account=generate_commutation_need_account,
        maybe_handle_cashflow_deterministic=_maybe_handle_cashflow_deterministic,
        maybe_handle_max_capital_request=_maybe_handle_max_capital_request,
        maybe_handle_fixation_documents_deterministic=_maybe_handle_fixation_documents_deterministic,
        maybe_handle_commutation_deterministic=_maybe_handle_commutation_deterministic,
        compute_analysis_default_retirement_age=_compute_analysis_default_retirement_age,
        maybe_handle_termination_deterministic=_maybe_handle_termination_deterministic,
        maybe_handle_approval_or_cancel_flow=_maybe_handle_approval_or_cancel_flow,
        apply_wants_ignore_blocked_and_portfolio_analysis_messages=_apply_wants_ignore_blocked_and_portfolio_analysis_messages,
        log_llm_event=log_llm_event,
        build_streaming_response_generate_loop=_build_streaming_response_generate_loop,
        build_restore_snapshot_banner=_build_restore_snapshot_banner,
        stream_handle_explicit_transform=_stream_handle_explicit_transform,
        stream_generate_preamble=_stream_generate_preamble,
        build_history_messages_for_stream=_build_history_messages_for_stream,
        load_stream_intents_playbook_text=_load_stream_intents_playbook_text,
        get_retirement_kb_for_stream=get_retirement_kb_for_stream,
        stream_collect_llm_response_with_retry_or_yield_error=_stream_collect_llm_response_with_retry_or_yield_error,
        collect_llm_response_with_retry=_collect_llm_response_with_retry,
        get_llm_service=_get_llm_service,
        get_retry_settings=_get_retry_settings,
        maybe_apply_non_tool_response_guardrails=_maybe_apply_non_tool_response_guardrails,
        stream_finalize_non_tool_response=_stream_finalize_non_tool_response,
        build_allowed_sources_for_numeric_provenance=_build_allowed_sources_for_numeric_provenance,
        compute_final_out_with_numeric_provenance_guardrail=_compute_final_out_with_numeric_provenance_guardrail,
        postprocess_no_tools_user_visible_text=_postprocess_no_tools_user_visible_text,
        validate_execution_only_output=validate_execution_only_output,
        build_exec_only_rewrite_prompt=build_exec_only_rewrite_prompt,
        build_execution_only_fallback=build_execution_only_fallback,
        enforce_behavioral_limits=enforce_behavioral_limits,
        sanitize_words_only_output=sanitize_words_only_output,
        sanitize_words_only_conceptual=sanitize_words_only_conceptual,
        stream_handle_tool_call_iteration=_stream_handle_tool_call_iteration,
        stream_prepare_tool_call_and_maybe_request_commutation_approval=_stream_prepare_tool_call_and_maybe_request_commutation_approval,
        stream_execute_tool_and_process_result=_stream_execute_tool_and_process_result,
        is_tool_error_text=_is_tool_error_text,
        execution_only_blocked=execution_only_blocked,
    )
