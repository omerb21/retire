from app.schemas.llm_chat import ChatRequest
from app.services.llm_chat.numeric_provenance import validate_reply_numeric_provenance
from app.services.llm_chat.orchestration_utils import sanitize_user_visible_text
from app.utils.llm_chat_log import log_llm_event


def _compute_final_out_with_numeric_provenance_guardrail(
    *,
    req_id: str,
    request: ChatRequest,
    full_response: str,
    allowed_sources: list[str],
    is_portfolio_analysis: bool,
):
    violation = validate_reply_numeric_provenance(
        reply_text=full_response,
        allowed_source_texts=allowed_sources,
    )
    if violation is not None:
        try:
            log_llm_event(
                request_id=req_id,
                event_type="numeric_provenance_violation",
                payload={"tokens": list(violation.tokens)},
                client_id=request.client_id,
                extra={"endpoint": "stream"},
            )
        except Exception:
            pass
        final_out = (
            "שגיאה: המערכת חסמה תשובה שכללה מספרים שלא הגיעו מחישוב מערכת. "
            "כדי לקבל מספרים, בקש לבצע חישוב/דוח דרך הכלים של המערכת."
        )
    else:
        final_out = sanitize_user_visible_text(full_response)
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
