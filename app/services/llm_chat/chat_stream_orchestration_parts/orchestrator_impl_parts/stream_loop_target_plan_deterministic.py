from fastapi.responses import StreamingResponse

from app.schemas.llm_chat import ChatRequest
from app.services.llm_chat.message_utils import extract_target_pension_from_message

from ..chat_helpers import _last_assistant_message_text
from ..stream_system_prompt_generators import generate_target_plan


def _maybe_handle_target_plan_deterministic(
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
    wants_execute_target_plan: bool,
    stream_request_id: str,
):
    last_assistant_text = _last_assistant_message_text(request.messages)
    awaiting_target_plan_gross_net = False
    if last_assistant_text:
        lowered_assistant = last_assistant_text.lower()
        awaiting_target_plan_gross_net = (
            ("תכנית יעד קצבה" in lowered_assistant or "תכנית יעד" in lowered_assistant)
            and ("ברוטו" in lowered_assistant)
            and ("נטו" in lowered_assistant)
        )

    explicit_target_plan_request = False
    try:
        if ("תזרים" not in lowered_user_msg) and ("cashflow" not in lowered_user_msg):
            planning_keywords = (
                "יעד קצבה",
                "תכנית",
                "תוכנית",
                "מתווה",
                "בנה",
                "צור",
                "תכנן",
                "תכנון",
                "build_target_pension_plan",
            )
            if any(k in lowered_user_msg for k in planning_keywords):
                extracted_target = float(
                    extract_target_pension_from_message(original_user_msg) or 0
                )
                explicit_target_plan_request = extracted_target > 0
    except Exception:
        explicit_target_plan_request = False

    if (
        request.client_id is not None
        and (explicit_target_plan_request or awaiting_target_plan_gross_net)
        and (not is_doc_request)
        and (not is_qa_mode)
        and (not no_tools_requested)
        and (not wants_execute_target_plan)
    ):
        return StreamingResponse(
            generate_target_plan(
                computed_data=computed_data,
                original_user_msg=original_user_msg,
                request=request,
                db=db,
                effective_portfolio=effective_portfolio,
                stream_request_id=stream_request_id,
            ),
            media_type="text/plain",
        )

    return None
