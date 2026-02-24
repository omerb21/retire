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
    inline_tool_blocks = extract_inline_tool_output_blocks(full_response)
    if inline_tool_blocks:
        tool_only_text = "\n\n".join(
            b for b in inline_tool_blocks if isinstance(b, str) and b.strip()
        ).strip()
        safe_user_out = (
            tool_only_text
            + "\n\n"
            + "הפקתי את תוצאות הניתוח מהמערכת. אם תרצה שאסביר במילים בלי מספרים מה המשמעות, כתוב: הסבר במילים.\n"
        )
        return sanitize_user_visible_text(safe_user_out)

    scrubbed_response = sanitize_transparency_and_risk_blocks(full_response)
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
                "numeric_provenance_detected stream trace_id=%s request_id=%s client_id=%s tokens=%s matches=%s preview_head=%s preview_tail=%s",
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
                event_type="numeric_provenance_violation_detected",
                payload={
                    "tokens": list(violation.tokens),
                    "matches": matches,
                    "preview_head": head_preview,
                    "preview_tail": tail_preview,
                },
                client_id=request.client_id,
                extra={
                    "endpoint": "stream",
                    "trace_id": trace_id,
                },
            )
        except Exception:
            pass

        try:
            from app.services.agent_trace_logger import log_trace_event

            log_trace_event(
                event_type="numeric_provenance_violation_detected",
                payload={
                    "tokens": list(violation.tokens),
                    "matches": matches,
                    "preview_head": head_preview,
                    "preview_tail": tail_preview,
                    "request_id": req_id,
                },
                client_id=request.client_id,
                endpoint="stream",
            )
        except Exception:
            pass

    final_out = sanitize_user_visible_text(scrubbed_response)
    if is_portfolio_analysis and isinstance(final_out, str) and final_out.strip():
        final_out = "\n".join(
            ln for ln in final_out.splitlines() if "מדרגות מס" not in ln
        )
    if is_portfolio_analysis and isinstance(final_out, str) and final_out.strip():
        if (
            "הערכה" not in final_out
            and "הערכה גסה" not in final_out
            and "ראשונית" not in final_out
        ):
            final_out = (
                "הערה: התרחישים האוטומטיים הם הערכה ראשונית/גסה בלבד ואינם חישוב ביצוע מדויק.\n\n"
                + final_out
            )
    return final_out
