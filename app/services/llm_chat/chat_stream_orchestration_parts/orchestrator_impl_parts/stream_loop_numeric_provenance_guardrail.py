import logging

from app.schemas.llm_chat import ChatRequest
from app.services.llm_chat.numeric_provenance import (
    extract_inline_tool_output_blocks,
    extract_numeric_matches,
    sanitize_transparency_and_risk_blocks,
    validate_reply_numeric_provenance,
)
from app.services.llm_chat.orchestration_utils import sanitize_user_visible_text
from app.utils.llm_chat_log import log_llm_event
from app.utils.trace_context import get_current_trace_id


logger = logging.getLogger("app.llm_chat")


def _compute_final_out_with_numeric_provenance_guardrail(
    *,
    req_id: str,
    request: ChatRequest,
    full_response: str,
    allowed_sources: list[str],
    is_portfolio_analysis: bool,
):
    scrubbed_response = sanitize_transparency_and_risk_blocks(full_response)
    inline_tool_blocks = extract_inline_tool_output_blocks(full_response)
    effective_allowed_sources = list(allowed_sources or []) + inline_tool_blocks

    violation = validate_reply_numeric_provenance(
        reply_text=scrubbed_response,
        allowed_source_texts=effective_allowed_sources,
    )
    if violation is not None:
        trace_id = get_current_trace_id()
        matches = extract_numeric_matches(full_response)
        head_preview = full_response[:300] if isinstance(full_response, str) else ""
        tail_preview = full_response[-300:] if isinstance(full_response, str) else ""

        try:
            logger.warning(
                "numeric_provenance_blocked stream trace_id=%s request_id=%s client_id=%s tokens=%s matches=%s preview_head=%s preview_tail=%s",
                trace_id,
                req_id,
                getattr(request, "client_id", None),
                list(getattr(violation, "tokens", ()) or ()),
                matches,
                head_preview,
                tail_preview,
            )
        except Exception:
            pass
        try:
            log_llm_event(
                request_id=req_id,
                event_type="numeric_provenance_violation",
                payload={
                    "tokens": list(violation.tokens),
                    "matches": matches,
                    "blocked_preview_head": head_preview,
                    "blocked_preview_tail": tail_preview,
                },
                client_id=request.client_id,
                extra={
                    "endpoint": "stream",
                    "trace_id": trace_id,
                },
            )
        except Exception:
            pass
        final_out = (
            "שגיאה: המערכת חסמה תשובה שכללה מספרים שלא הגיעו מחישוב מערכת. "
            "כדי לקבל מספרים, בקש לבצע חישוב/דוח דרך הכלים של המערכת."
        )
    else:
        final_out = sanitize_user_visible_text(scrubbed_response)
    if is_portfolio_analysis and isinstance(final_out, str) and final_out.strip():
        final_out = "\n".join(
            ln for ln in final_out.splitlines() if "מדרגות מס" not in ln
        )
    if is_portfolio_analysis and isinstance(final_out, str) and final_out.strip():
        if "הערכה" not in final_out and "הערכה גסה" not in final_out and "ראשונית" not in final_out:
            final_out = (
                "הערה: התרחישים האוטומטיים הם הערכה ראשונית/גסה בלבד ואינם חישוב ביצוע מדויק.\n\n"
                + final_out
            )
    return final_out
