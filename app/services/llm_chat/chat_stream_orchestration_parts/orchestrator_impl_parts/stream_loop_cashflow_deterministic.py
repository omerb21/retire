from fastapi.responses import StreamingResponse

from app.schemas.llm_chat import ChatRequest
from app.services.llm_chat.orchestration_utils import is_cashflow_missing_income_followup

from ..stream_system_prompt_generators import generate_cashflow


def _maybe_handle_cashflow_deterministic(
    *,
    request: ChatRequest,
    db,
    computed_data,
    effective_portfolio,
    original_user_msg: str,
    lowered_user_msg: str,
    is_doc_request: bool,
    is_qa_mode: bool,
    no_tools_requested: bool,
    commutation_intent: bool,
    force_max_exemption: bool,
    stream_request_id: str,
):
    explicit_cashflow_request = ("תזרים" in lowered_user_msg) or ("cashflow" in lowered_user_msg)

    wants_cashflow_refresh = is_cashflow_missing_income_followup(original_user_msg)

    if (
        (explicit_cashflow_request or wants_cashflow_refresh)
        and request.client_id is not None
        and (not is_doc_request)
        and (not is_qa_mode)
        and (not no_tools_requested)
        and (not commutation_intent)
    ):
        return StreamingResponse(
            generate_cashflow(
                computed_data=computed_data,
                original_user_msg=original_user_msg,
                request=request,
                db=db,
                effective_portfolio=effective_portfolio,
                force_max_exemption=force_max_exemption,
                stream_request_id=stream_request_id,
            ),
            media_type="text/plain; charset=utf-8",
        )

    return None
