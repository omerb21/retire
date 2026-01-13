import json
import logging
import inspect
import importlib
import re
import uuid
import time
import threading
import queue
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
    clear_pending_approval_request,
    load_latest_target_pension_plan,
    run_tax_projection_autochain,
    store_latest_target_pension_plan,
)

from datetime import date
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
)
from app.services.llm_chat.portfolio_context import build_pension_portfolio_context
from app.services.llm_chat.orchestration_utils import (
    apply_max_exemption_if_requested,
    build_portfolio_wide_after_settlement_severance_transform_accounts_from_portfolio,
    build_portfolio_wide_component_transform_accounts_from_portfolio,
    build_portfolio_wide_education_fund_transform_accounts_from_portfolio,
    build_portfolio_wide_prev_employers_severance_transform_accounts_from_portfolio,
    build_targeted_component_transform_accounts_from_portfolio,
    build_partial_pension_transform_accounts_from_portfolio,
    build_transform_accounts_from_portfolio,
    build_tax_result_system_message_for_stream,
    build_tool_call_message_content,
    build_tool_result_system_message_for_stream,
    compute_default_retirement_date_for_tool_call,
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
    normalize_retirement_date_if_jan1_placeholder,
    parse_tool_call_from_reply,
    sanitize_user_visible_text,
)
from app.services.llm_chat.chat_orchestration_helpers import maybe_clear_pension_portfolio_after_transform
from app.services.llm_chat.numeric_provenance import validate_reply_numeric_provenance
from app.services.pension_portfolio.snapshot_loader import (
    load_latest_pension_portfolio_snapshot_models,
)
from app.models.client import Client
from app.models import CurrentEmployer, EmployerGrant, GrantType
from app.utils.llm_chat_log import (
    generate_request_id,
    log_llm_event,
    set_current_case_id,
    set_current_request_id,
)
from app.services.llm_agent_tools_service import AgentToolsService
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

logger = logging.getLogger(__name__)

PC_LLM_MAX_RETRIES = 3
PC_LLM_TIMEOUT_SECONDS = 120.0
PC_LLM_BACKOFF_SECONDS = (0.75, 1.5, 3.0)


def run_pension_chat_stream(request: ChatRequest, db: Session) -> StreamingResponse:
    stream_request_id = generate_request_id()
    set_current_request_id(stream_request_id)

    effective_portfolio = request.pension_portfolio
    effective_snapshot_at = request.pension_portfolio_snapshot_at
    if request.client_id is not None:
        loaded = _load_latest_pension_portfolio_snapshot_models(db, request.client_id)
        if loaded is not None:
            effective_portfolio, effective_snapshot_at = loaded
            try:
                logger.info(
                    "📦 Using DB pension_portfolio_snapshot (client_id=%s, accounts=%s, snapshot_at=%s)",
                    request.client_id,
                    len(effective_portfolio),
                    effective_snapshot_at,
                )
            except Exception:
                pass

    messages, computed_data = prepare_messages_with_context(request, db)

    original_user_msg = find_last_user_message(request.messages)

    try:
        case_router = importlib.import_module("app.services.llm_chat.case_router")
        select_case = getattr(case_router, "select_case", None)
        if callable(select_case):
            decision = select_case(
                user_message=original_user_msg,
                messages=messages,
                client_id=request.client_id,
            )
            case_id = getattr(decision, "case_id", None)
            set_current_case_id(case_id or "interactive_readonly")
        else:
            set_current_case_id("interactive_readonly")
    except Exception:
        set_current_case_id("interactive_readonly")

    if request.client_id is not None and (
        _is_target_plan_adjust_request(original_user_msg)
        or _is_target_plan_adjust_followup(original_user_msg, request.messages)
    ):
        payload = extract_latest_target_pension_plan_payload(request.messages)
        if payload is None:
            payload = load_latest_target_pension_plan(db=db, client_id=request.client_id)

        return StreamingResponse(
            generate_adjust_reply(
                computed_data=computed_data,
                payload=payload,
                original_user_msg=original_user_msg,
                request=request,
                db=db,
                effective_portfolio=effective_portfolio,
                stream_request_id=stream_request_id,
            ),
            media_type="text/plain; charset=utf-8",
        )

    if request.client_id is not None and _is_system_results_request(original_user_msg):
        return StreamingResponse(
            generate_system_results(
                computed_data=computed_data,
                original_user_msg=original_user_msg,
                request=request,
                db=db,
                effective_portfolio=effective_portfolio,
                stream_request_id=stream_request_id,
            ),
            media_type="text/plain; charset=utf-8",
        )

    if request.client_id is not None and _is_system_inventory_request(original_user_msg):
        return StreamingResponse(
            generate_system_inventory(
                computed_data=computed_data,
                request=request,
                db=db,
                effective_portfolio=effective_portfolio,
                stream_request_id=stream_request_id,
            ),
            media_type="text/plain; charset=utf-8",
        )

    if request.client_id is not None and is_data_awareness_request(original_user_msg):
        return StreamingResponse(
            generate_data_awareness(
                computed_data=computed_data,
                request=request,
                db=db,
                effective_portfolio=effective_portfolio,
                effective_snapshot_at=effective_snapshot_at,
                stream_request_id=stream_request_id,
            ),
            media_type="text/plain; charset=utf-8",
        )

    if request.client_id is not None and is_list_all_financial_entities_request(original_user_msg):
        return StreamingResponse(
            generate_list_all_entities(
                computed_data=computed_data,
                request=request,
                db=db,
                effective_portfolio=effective_portfolio,
                effective_snapshot_at=effective_snapshot_at,
                stream_request_id=stream_request_id,
            ),
            media_type="text/plain; charset=utf-8",
        )
    if is_portfolio_breakdown_request(original_user_msg):
        portfolio = effective_portfolio or []
        if portfolio:

            return StreamingResponse(
                generate_breakdown(
                    computed_data=computed_data,
                    portfolio=portfolio,
                    original_user_msg=original_user_msg,
                    effective_snapshot_at=effective_snapshot_at,
                ),
                media_type="text/plain; charset=utf-8",
            )

    if is_portfolio_analysis_request(original_user_msg):
        portfolio = effective_portfolio or []
        if portfolio:

            return StreamingResponse(
                generate_portfolio_analysis(
                    computed_data=computed_data,
                    request=request,
                    db=db,
                    portfolio=portfolio,
                    original_user_msg=original_user_msg,
                    effective_snapshot_at=effective_snapshot_at,
                ),
                media_type="text/plain; charset=utf-8",
            )

    is_net_request = is_net_pension_request(original_user_msg)
    is_doc_request = is_document_request(original_user_msg)
    is_tax_doc_request = is_tax_documents_request(original_user_msg)
    is_qa_mode = is_qa_request(original_user_msg)
    no_tools_requested = is_no_tools_request(original_user_msg)
    force_max_exemption = is_max_exemption_request(original_user_msg)
    commutation_intent = is_pension_commutation_request(original_user_msg)
    explicit_transform = (not commutation_intent) and is_transform_request(original_user_msg)
    explicit_termination = is_process_termination_request(original_user_msg)
    termination_change = is_termination_change_request(original_user_msg)
    is_cashflow_request = is_retirement_cashflow_request(original_user_msg)
    is_comparison_request = is_retirement_comparison_request(original_user_msg)
    is_portfolio_analysis = is_portfolio_analysis_request(original_user_msg)

    lowered_user_msg = (original_user_msg or "").lower()
    wants_capital_transform = (
        (
            ("להון" in lowered_user_msg)
            or ("to capital" in lowered_user_msg)
            or ("הונית" in lowered_user_msg)
            or ("הוני" in lowered_user_msg)
            or ("מקסימום הון" in lowered_user_msg)
        )
        and ("המר" in lowered_user_msg or "המרה" in lowered_user_msg or "convert" in lowered_user_msg or "משיכה" in lowered_user_msg or "משוך" in lowered_user_msg)
    )
    wants_execute_target_plan = (
        "בצע" in lowered_user_msg
        and ("תכנית" in lowered_user_msg or "תוכנית" in lowered_user_msg or "מתווה" in lowered_user_msg)
    )
    wants_fixation_execute = (
        "בצע" in lowered_user_msg
        and ("קיבוע" in lowered_user_msg)
        and ("זכויות" in lowered_user_msg)
    )

    wants_fixation_documents = bool(
        is_tax_doc_request
        and any(token in lowered_user_msg for token in ("קיבוע", "זכויות", "161ד", "161d"))
    )

    explicit_cashflow_request = ("תזרים" in lowered_user_msg) or ("cashflow" in lowered_user_msg)

    wants_cashflow_refresh = is_cashflow_missing_income_followup(original_user_msg)

    if (
        request.client_id is not None
        and is_doc_request
        and (not is_tax_doc_request)
        and (not is_qa_mode)
        and (not no_tools_requested)
    ):
        wants_pdf = "pdf" in lowered_user_msg
        return _stream_execute_tool_no_approval(
            "GENERATE_FULL_REPORT",
            {
                "output_format": "pdf" if wants_pdf else "html",
                "report_type": "full",
                "ensure_analysis": False,
            },
            computed_data=computed_data,
            client_id=request.client_id,
            db=db,
            effective_portfolio=effective_portfolio,
            force_max_exemption=force_max_exemption,
            stream_request_id=stream_request_id,
            is_portfolio_analysis=is_portfolio_analysis,
        )

    target_plan_response = _maybe_handle_target_plan_deterministic(
        request=request,
        db=db,
        computed_data=computed_data,
        effective_portfolio=effective_portfolio,
        original_user_msg=original_user_msg,
        lowered_user_msg=lowered_user_msg,
        is_doc_request=is_doc_request,
        is_qa_mode=is_qa_mode,
        no_tools_requested=no_tools_requested,
        wants_execute_target_plan=wants_execute_target_plan,
        stream_request_id=stream_request_id,
    )
    if target_plan_response is not None:
        return target_plan_response

    if commutation_intent and request.client_id is not None:
        account_number = _extract_commutation_account_number(original_user_msg)
        if not account_number:
            return StreamingResponse(
                generate_commutation_need_account(computed_data=computed_data),
                media_type="text/plain; charset=utf-8",
            )

    cashflow_response = _maybe_handle_cashflow_deterministic(
        request=request,
        db=db,
        computed_data=computed_data,
        effective_portfolio=effective_portfolio,
        original_user_msg=original_user_msg,
        lowered_user_msg=lowered_user_msg,
        is_doc_request=is_doc_request,
        is_qa_mode=is_qa_mode,
        no_tools_requested=no_tools_requested,
        commutation_intent=commutation_intent,
        force_max_exemption=force_max_exemption,
        stream_request_id=stream_request_id,
    )
    if cashflow_response is not None:
        return cashflow_response

    max_capital_response = _maybe_handle_max_capital_request(
        request=request,
        db=db,
        original_user_msg=original_user_msg,
        lowered_user_msg=lowered_user_msg,
        explicit_termination=explicit_termination,
        is_doc_request=is_doc_request,
        is_qa_mode=is_qa_mode,
        no_tools_requested=no_tools_requested,
        computed_data=computed_data,
        effective_portfolio=effective_portfolio,
        force_max_exemption=force_max_exemption,
        stream_request_id=stream_request_id,
    )
    if max_capital_response is not None:
        return max_capital_response

    fixation_documents_response = _maybe_handle_fixation_documents_deterministic(
        request=request,
        db=db,
        wants_fixation_documents=wants_fixation_documents,
        is_qa_mode=is_qa_mode,
        no_tools_requested=no_tools_requested,
        computed_data=computed_data,
        effective_portfolio=effective_portfolio,
        force_max_exemption=force_max_exemption,
        stream_request_id=stream_request_id,
        is_portfolio_analysis=is_portfolio_analysis,
    )
    if fixation_documents_response is not None:
        return fixation_documents_response

    # Early deterministic handling for pension commutation requests.
    # Only run this path when the user provided a specific account identifier.
    # If the request is vague (no account number), fall back to the LLM flow.
    commutation_response = _maybe_handle_commutation_deterministic(
        commutation_intent=commutation_intent,
        request=request,
        is_doc_request=is_doc_request,
        is_qa_mode=is_qa_mode,
        original_user_msg=original_user_msg,
        db=db,
        effective_portfolio=effective_portfolio,
        computed_data=computed_data,
    )
    if commutation_response is not None:
        return commutation_response

    analysis_default_retirement_age = _compute_analysis_default_retirement_age(
        request=request,
        db=db,
        is_portfolio_analysis=is_portfolio_analysis,
    )

    termination_already_executed, termination_response = _maybe_handle_termination_deterministic(
        request=request,
        db=db,
        original_user_msg=original_user_msg,
        explicit_termination=explicit_termination,
        termination_change=termination_change,
        no_tools_requested=no_tools_requested,
        is_qa_mode=is_qa_mode,
        wants_execute_target_plan=wants_execute_target_plan,
        wants_fixation_execute=wants_fixation_execute,
        computed_data=computed_data,
        effective_portfolio=effective_portfolio,
        force_max_exemption=force_max_exemption,
        stream_request_id=stream_request_id,
        is_portfolio_analysis=is_portfolio_analysis,
    )
    if termination_response is not None:
        return termination_response

    approval_response = _maybe_handle_approval_or_cancel_flow(
        request=request,
        db=db,
        no_tools_requested=no_tools_requested,
        computed_data=computed_data,
        termination_already_executed=termination_already_executed,
        termination_change=termination_change,
        wants_execute_target_plan=wants_execute_target_plan,
        original_user_msg=original_user_msg,
        effective_portfolio=effective_portfolio,
        force_max_exemption=force_max_exemption,
        stream_request_id=stream_request_id,
        is_portfolio_analysis=is_portfolio_analysis,
        is_doc_request=is_doc_request,
        is_qa_mode=is_qa_mode,
    )
    if approval_response is not None:
        return approval_response

    wants_ignore_blocked = _apply_wants_ignore_blocked_and_portfolio_analysis_messages(
        request=request,
        messages=messages,
        is_portfolio_analysis=is_portfolio_analysis,
    )

    log_llm_event(
        request_id=stream_request_id,
        event_type="user_message",
        payload=original_user_msg,
        client_id=request.client_id,
        extra={"endpoint": "stream"},
    )

    def generate(force_max_exemption_val: bool, req_id: str):
        if computed_data is not None:
            computed_json = json.dumps(
                {"type": "computed_data", "data": computed_data.model_dump()},
                ensure_ascii=False,
            )
            yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"

        current_pension_portfolio = effective_portfolio

        if explicit_transform and (not no_tools_requested) and (not is_doc_request) and (not is_qa_mode):
            yield from _stream_handle_explicit_transform(
                lowered_user_msg=lowered_user_msg,
                original_user_msg=original_user_msg,
                current_pension_portfolio=current_pension_portfolio,
                request=request,
                db=db,
                req_id=req_id,
                wants_capital_transform=wants_capital_transform,
            )
            return

        report_open_path: str | None = None
        qa_summary_required = False
        qa_summary_satisfied = False
        executed_tools: set[str] = set()
        forced_fixation_chain_done = False

        required_tools: set[str] = set()
        if not no_tools_requested:
            if is_doc_request:
                if is_tax_doc_request:
                    required_tools.add("GENERATE_TAX_DEDUCTION_DOCUMENTS")
                else:
                    required_tools.add("GENERATE_FULL_REPORT")

        tool_call_marker = "###TOOL_CALL###"
        max_steps = 5
        current_step = 0

        history_messages: list[ChatMessage] = list(messages)

        if wants_ignore_blocked:
            history_messages.append(
                ChatMessage(
                    role="system",
                    content=(
                        "המשתמש אישר להתעלם מיתרות חסומות/יתרות לטיפול במסך עזיבת עבודה ולהמשיך בחישוב רק על מה שניתן. "
                        "אל תשאל שוב לאישור על זה. אל תבצע עזיבת עבודה בשיחה זו, והמשך עם שאר הכלים הרלוונטיים בלבד."
                    ),
                )
            )

        while current_step < max_steps:
            current_step += 1

            should_break, full_response = yield from _stream_collect_llm_response_with_retry_or_yield_error(
                collect_llm_response_with_retry=_collect_llm_response_with_retry,
                history_messages=history_messages,
                client_id=request.client_id,
                stream_request_id=stream_request_id,
                current_step=current_step,
                logger=logger,
                get_llm_service=_get_llm_service,
                get_retry_settings=_get_retry_settings,
            )
            if should_break:
                break

            if tool_call_marker not in full_response:
                should_continue, has_pass_fail = _maybe_apply_non_tool_response_guardrails(
                    full_response=full_response,
                    request=request,
                    db=db,
                    history_messages=history_messages,
                    is_qa_mode=is_qa_mode,
                    no_tools_requested=no_tools_requested,
                    required_tools=required_tools,
                    executed_tools=executed_tools,
                    is_tax_doc_request=is_tax_doc_request,
                    qa_summary_required=qa_summary_required,
                    is_cashflow_request=is_cashflow_request,
                    is_comparison_request=is_comparison_request,
                    is_net_request=is_net_request,
                    is_doc_request=is_doc_request,
                )
                if should_continue:
                    continue

                log_llm_event(
                    request_id=req_id,
                    event_type="final_answer",
                    payload=full_response,
                    client_id=request.client_id,
                    extra={"endpoint": "stream"},
                )
                if qa_summary_required and has_pass_fail:
                    qa_summary_satisfied = True

                allowed_sources = _build_allowed_sources_for_numeric_provenance(
                    request=request,
                    history_messages=history_messages,
                )
                final_out = _compute_final_out_with_numeric_provenance_guardrail(
                    req_id=req_id,
                    request=request,
                    full_response=full_response,
                    allowed_sources=allowed_sources,
                    is_portfolio_analysis=is_portfolio_analysis,
                )
                yield final_out
                break

            try:
                (
                    should_continue,
                    should_break,
                    should_return,
                    tool_name,
                    tool_args,
                    current_pension_portfolio,
                ) = yield from _stream_prepare_tool_call_and_maybe_request_commutation_approval(
                    full_response=full_response,
                    request=request,
                    db=db,
                    req_id=req_id,
                    history_messages=history_messages,
                    original_user_msg=original_user_msg,
                    is_portfolio_analysis=is_portfolio_analysis,
                    analysis_default_retirement_age=analysis_default_retirement_age,
                    no_tools_requested=no_tools_requested,
                    is_qa_mode=is_qa_mode,
                    is_doc_request=is_doc_request,
                    is_tax_doc_request=is_tax_doc_request,
                    wants_ignore_blocked=wants_ignore_blocked,
                    explicit_termination=explicit_termination,
                    termination_already_executed=termination_already_executed,
                    termination_change=termination_change,
                    current_pension_portfolio=current_pension_portfolio,
                    wants_capital_transform=wants_capital_transform,
                    force_max_exemption_val=force_max_exemption_val,
                )
                if should_continue:
                    continue
                if should_break:
                    break
                if should_return:
                    return

                (
                    should_break,
                    qa_summary_required,
                    report_open_path,
                    current_pension_portfolio,
                    forced_fixation_chain_done,
                ) = yield from _stream_execute_tool_and_process_result(
                    logger=logger,
                    req_id=req_id,
                    request=request,
                    db=db,
                    tool_name=tool_name,
                    tool_args=tool_args,
                    current_pension_portfolio=current_pension_portfolio,
                    force_max_exemption_val=force_max_exemption_val,
                    full_response=full_response,
                    qa_summary_required=qa_summary_required,
                    report_open_path=report_open_path,
                    forced_fixation_chain_done=forced_fixation_chain_done,
                    required_tools=required_tools,
                    executed_tools=executed_tools,
                    is_tax_doc_request=is_tax_doc_request,
                    is_qa_mode=is_qa_mode,
                    history_messages=history_messages,
                )
                if should_break:
                    break

                # IMPORTANT: After we stream any tool output, we end the stream immediately.
                # This prevents the model from appending post-tool narrative that may include
                # unprovenanced numbers and get blocked by the numeric provenance guardrail.
                #
                # Exception: in QA mode, after generating a full report, we must continue
                # streaming to allow the model to emit the final QA summary.
                if not qa_summary_required:
                    yield (
                        "\n\n"
                        + "הפקתי את תוצאות הניתוח מהמערכת. אם תרצה שאסביר במילים בלי מספרים מה המשמעות, כתוב: הסבר במילים.\n"
                    )
                    return

            except Exception as e:
                logger.error("Stream Tool Execution Failed: %s", e, exc_info=True)
                yield f"\n\n(Error executing tool: {sanitize_user_visible_text(str(e))})"
                break

        if qa_summary_required and not qa_summary_satisfied:
            if report_open_path:
                yield (
                    "\n\nFAIL - לא התקבלה תשובת QA סופית מהמודל לאחר יצירת הדוח. "
                    f"open_path: {report_open_path}"
                )
            else:
                yield "\n\nFAIL - לא התקבלה תשובת QA סופית מהמודל לאחר יצירת הדוח."

        if not no_tools_requested:
            missing_tools_final = required_tools.difference(executed_tools)
            if missing_tools_final:
                yield (
                    "\n\nFAIL - לא הושלמו שלבי החובה לבקשה. חסרים הכלים: "
                    + ", ".join(sorted(missing_tools_final))
                )

    return StreamingResponse(
        generate(force_max_exemption, stream_request_id),
        media_type="text/plain; charset=utf-8",
    )
