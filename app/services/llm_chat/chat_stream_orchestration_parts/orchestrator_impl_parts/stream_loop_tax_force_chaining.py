from app.schemas.llm_chat import ChatRequest
from app.services.llm_chat.chat_orchestration_helpers import (
    get_gross_for_tax_chaining,
    run_tax_projection_autochain,
)
from app.services.llm_chat.message_utils import find_last_user_message
from app.services.llm_chat.orchestration_utils import (
    is_document_request,
    is_net_pension_request,
)

from ..stream_tool_execution import _execute_tool_call


def _maybe_run_tax_force_chaining(
    *,
    logger,
    req_id: str,
    request: ChatRequest,
    tool_db,
    tool_name: str,
    tool_result: str,
    current_pension_portfolio,
    force_max_exemption_val,
):
    current_user_msg = find_last_user_message(request.messages)
    is_net = is_net_pension_request(current_user_msg)
    is_doc = is_document_request(current_user_msg)

    logger.info(
        "🔗 Checking Force Chaining (Stream): Tool=%s, IsNet=%s, Msg='%s'",
        tool_name,
        is_net,
        current_user_msg[:50],
    )

    gross_for_tax = get_gross_for_tax_chaining(
        is_net=is_net,
        tool_name=tool_name,
        tool_result=tool_result,
    )

    logger.info(
        "🔗 Force Chaining (Stream): Tool=%s, IsNet=%s, GrossForTax=%s",
        tool_name,
        is_net,
        gross_for_tax,
    )

    tax_result = run_tax_projection_autochain(
        gross_for_tax=gross_for_tax,
        execute_tool_call_fn=lambda name, args: _execute_tool_call(
            name,
            args,
            request.client_id,
            tool_db,
            pension_portfolio=current_pension_portfolio,
            force_max_exemption=force_max_exemption_val,
            request_id=req_id,
        ),
    )

    return gross_for_tax, tax_result
