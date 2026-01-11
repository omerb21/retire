from typing import Any

from app.schemas.llm_chat import ChatRequest
from app.services.llm_chat.chat_orchestration_helpers import build_approval_request_ui_action

from ..stream_top_level_helpers import _store_pending_approval_request


def _stream_maybe_request_commutation_approval(
    *,
    tool_name,
    tool_args,
    request: ChatRequest,
    db,
):
    if tool_name in {"EXECUTE_PENSION_COMMUTATION", "SUBMIT_TAX_COMMUTATION"}:
        reason = "נדרש אישור לפני ביצוע פעולה במערכת."
        if tool_name == "EXECUTE_PENSION_COMMUTATION":
            reason = "נדרש אישור לפני ביצוע היוון קצבה במערכת."
        if tool_name == "SUBMIT_TAX_COMMUTATION":
            reason = "נדרש אישור לפני הגשת/ביצוע קיבוע/פריסה במערכת."

        try:
            _store_pending_approval_request(
                db=db,
                client_id=request.client_id,
                tool_name=tool_name,
                tool_args=tool_args,
            )
        except Exception:
            pass

        yield build_approval_request_ui_action(
            tool_name=tool_name,
            tool_args=tool_args if isinstance(tool_args, dict) else {},
            reason=reason,
            risk_level="high",
            rag_sources=None,
        )
        return True

    return False
