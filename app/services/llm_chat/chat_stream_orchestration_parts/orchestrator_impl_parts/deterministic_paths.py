from __future__ import annotations

import importlib
import json

from fastapi.responses import StreamingResponse

from app.schemas.llm_chat import ChatMessage
from app.services.llm_chat.message_utils import (
    extract_latest_target_pension_plan_payload,
    find_last_user_message,
)
from app.services.llm_chat.orchestration_utils import (
    extract_desired_monthly_income_from_text,
    infer_desired_income_is_net_explicit,
    is_cashflow_missing_income_followup,
    is_data_awareness_request,
    is_document_request,
    is_list_all_financial_entities_request,
    is_max_capital_request,
    is_max_exemption_request,
    is_net_pension_request,
    is_no_tools_request,
    is_pension_commutation_request,
    is_portfolio_analysis_request,
    is_portfolio_breakdown_request,
    is_process_termination_request,
    is_qa_request,
    is_retirement_cashflow_request,
    is_retirement_comparison_request,
    is_tax_documents_request,
    is_transform_request,
)
from app.services.llm_chat.portfolio_context import build_pension_portfolio_context
from app.utils.llm_chat_log import log_llm_event, set_current_case_id

from .types import StreamCtx


def maybe_handle_deterministic_paths(ctx: StreamCtx) -> StreamingResponse | None:
    # Case routing (best effort)
    try:
        case_router = importlib.import_module("app.services.llm_chat.case_router")
        select_case = getattr(case_router, "select_case", None)
        if callable(select_case):
            decision = select_case(
                user_message=ctx.original_user_msg,
                messages=ctx.messages,
                client_id=ctx.request.client_id,
            )
            case_id = getattr(decision, "case_id", None)
            set_current_case_id(case_id or "interactive_readonly")
        else:
            set_current_case_id("interactive_readonly")
    except Exception:
        set_current_case_id("interactive_readonly")

    # --- Derived flags (moved 1:1) ---
    ctx.is_net_request = is_net_pension_request(ctx.original_user_msg)
    ctx.is_doc_request = is_document_request(ctx.original_user_msg)
    ctx.is_tax_doc_request = is_tax_documents_request(ctx.original_user_msg)
    ctx.is_qa_mode = is_qa_request(ctx.original_user_msg)
    ctx.no_tools_requested = is_no_tools_request(ctx.original_user_msg)
    ctx.force_max_exemption = is_max_exemption_request(ctx.original_user_msg)
    ctx.commutation_intent = is_pension_commutation_request(ctx.original_user_msg)
    ctx.explicit_transform = (not ctx.commutation_intent) and is_transform_request(
        ctx.original_user_msg
    )
    ctx.explicit_termination = is_process_termination_request(ctx.original_user_msg)
    ctx.termination_change = False
    ctx.is_cashflow_request = is_retirement_cashflow_request(ctx.original_user_msg)
    ctx.is_comparison_request = is_retirement_comparison_request(ctx.original_user_msg)
    ctx.is_portfolio_analysis = is_portfolio_analysis_request(ctx.original_user_msg)

    ctx.lowered_user_msg = (ctx.original_user_msg or "").lower()

    ctx.wants_capital_transform = (
        ("להון" in ctx.lowered_user_msg)
        or ("to capital" in ctx.lowered_user_msg)
        or ("הונית" in ctx.lowered_user_msg)
        or ("הוני" in ctx.lowered_user_msg)
        or ("מקסימום הון" in ctx.lowered_user_msg)
    ) and (
        "המר" in ctx.lowered_user_msg
        or "המרה" in ctx.lowered_user_msg
        or "convert" in ctx.lowered_user_msg
        or "משיכה" in ctx.lowered_user_msg
        or "משוך" in ctx.lowered_user_msg
    )
    ctx.wants_execute_target_plan = "בצע" in ctx.lowered_user_msg and (
        "תכנית" in ctx.lowered_user_msg
        or "תוכנית" in ctx.lowered_user_msg
        or "מתווה" in ctx.lowered_user_msg
    )
    ctx.wants_fixation_execute = (
        "בצע" in ctx.lowered_user_msg
        and ("קיבוע" in ctx.lowered_user_msg)
        and ("זכויות" in ctx.lowered_user_msg)
    )

    ctx.wants_fixation_documents = bool(
        ctx.is_tax_doc_request
        and any(
            token in ctx.lowered_user_msg
            for token in ("קיבוע", "זכויות", "161ד", "161d")
        )
    )

    ctx.explicit_cashflow_request = ("תזרים" in ctx.lowered_user_msg) or (
        "cashflow" in ctx.lowered_user_msg
    )

    ctx.wants_cashflow_refresh = is_cashflow_missing_income_followup(
        ctx.original_user_msg
    )

    ctx.max_capital_request = (not ctx.explicit_termination) and is_max_capital_request(
        ctx.original_user_msg
    )
    ctx.wants_execute_max_capital = ctx.max_capital_request and (
        "בצע" in ctx.lowered_user_msg
    )

    # event log (same place as original, before streaming loop)
    log_llm_event(
        request_id=ctx.stream_request_id,
        event_type="user_message",
        payload=ctx.original_user_msg,
        client_id=ctx.request.client_id,
        extra={"endpoint": "stream"},
    )

    return None
