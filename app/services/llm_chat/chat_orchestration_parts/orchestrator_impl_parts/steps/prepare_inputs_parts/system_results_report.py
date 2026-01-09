from __future__ import annotations

from app.schemas.llm_chat import ChatResponse


def _maybe_handle_system_results_report(
    *,
    request,
    db,
    request_id: str,
    original_user_msg,
    effective_portfolio,
    computed_data,
    _execute_tool_call,
    sanitize_user_visible_text,
    format_tool_output_for_user_stream,
) -> ChatResponse | None:
    lowered_early = (original_user_msg or "").lower()
    is_system_results_report_request = (
        ("דוח" in lowered_early and "תוצאות" in lowered_early)
        or ("report" in lowered_early and "results" in lowered_early)
    )

    from app.services.llm_chat.orchestration_utils import (
        is_document_request,
        is_no_tools_request,
        is_qa_request,
        is_tax_documents_request,
    )

    if (
        request.client_id is not None
        and is_system_results_report_request
        and is_document_request(original_user_msg)
        and (not is_tax_documents_request(original_user_msg))
        and (not is_qa_request(original_user_msg))
        and (not is_no_tools_request(original_user_msg))
    ):
        wants_pdf = "pdf" in (lowered_early or "")
        tool_result = _execute_tool_call(
            "GENERATE_FULL_REPORT",
            {"output_format": "pdf" if wants_pdf else "html", "report_type": "full"},
            request.client_id,
            db,
            pension_portfolio=effective_portfolio,
            force_max_exemption=False,
            user_approved=True,
            request_id=request_id,
        )
        return ChatResponse(
            reply=sanitize_user_visible_text(
                format_tool_output_for_user_stream("GENERATE_FULL_REPORT", tool_result)
            ),
            computed_data=computed_data,
        )

    return None
