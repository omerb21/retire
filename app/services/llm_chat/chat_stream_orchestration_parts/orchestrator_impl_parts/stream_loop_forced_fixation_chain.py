from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.schemas.llm_chat import ChatMessage, ChatRequest
from app.services.llm_chat.chat_orchestration_helpers import (
    get_gross_for_tax_chaining,
    run_tax_projection_autochain,
)
from app.services.llm_chat.message_utils import (
    extract_target_pension_from_message,
    find_last_user_message,
)
from app.services.llm_chat.orchestration_utils import (
    build_tax_result_system_message_for_stream,
    build_tool_result_system_message_for_stream,
    format_tool_output_for_user_stream,
    sanitize_user_visible_text,
)

from ..chat_helpers import _infer_target_is_net, _user_requested_target_pension_plan


def _stream_run_forced_fixation_chain_if_needed(
    *,
    request: ChatRequest,
    db: Session,
    tool_db: Session,
    req_id: str,
    tool_name,
    current_pension_portfolio,
    force_max_exemption_val,
    history_messages: list[ChatMessage],
) -> bool:
    forced_fixation_chain_done = False

    user_msg_for_chain = find_last_user_message(request.messages) or ""
    user_wants_target_plan = _user_requested_target_pension_plan(user_msg_for_chain)
    if user_wants_target_plan and _infer_target_is_net(user_msg_for_chain):
        target_val = None
        try:
            target_val = float(
                extract_target_pension_from_message(user_msg_for_chain) or 0
            )
        except Exception:
            target_val = None
        if target_val and target_val > 0:
            from ..stream_tool_execution import _execute_tool_call

            fixation_result = _execute_tool_call(
                "CALCULATE_FIXATION_OF_RIGHTS",
                {"save_result": True},
                request.client_id,
                tool_db,
                pension_portfolio=current_pension_portfolio,
                force_max_exemption=False,
                agent_reply=None,
                user_approved=True,
                request_id=req_id,
            )
            yield (
                "\n\n🔧 **פלט כלי (קיבוע זכויות - שרשור חובה):**\n"
                + sanitize_user_visible_text(
                    format_tool_output_for_user_stream(
                        "CALCULATE_FIXATION_OF_RIGHTS",
                        fixation_result,
                    )
                )
            )
            history_messages.append(
                ChatMessage(
                    role="system",
                    content=build_tool_result_system_message_for_stream(
                        "CALCULATE_FIXATION_OF_RIGHTS",
                        fixation_result,
                    ),
                )
            )

            plan_result = _execute_tool_call(
                "BUILD_TARGET_PENSION_PLAN",
                {"target_monthly_pension": float(target_val), "target_is_net": True},
                request.client_id,
                tool_db,
                pension_portfolio=current_pension_portfolio,
                force_max_exemption=False,
                agent_reply=None,
                user_approved=True,
                request_id=req_id,
            )
            yield (
                "\n\n🔧 **פלט כלי (בניית תכנית קצבה - אחרי קיבוע זכויות):**\n"
                + sanitize_user_visible_text(
                    format_tool_output_for_user_stream(
                        "BUILD_TARGET_PENSION_PLAN",
                        plan_result,
                    )
                )
            )
            history_messages.append(
                ChatMessage(
                    role="system",
                    content=build_tool_result_system_message_for_stream(
                        "BUILD_TARGET_PENSION_PLAN",
                        plan_result,
                    ),
                )
            )

            gross_for_tax_after = get_gross_for_tax_chaining(
                is_net=True,
                tool_name="BUILD_TARGET_PENSION_PLAN",
                tool_result=plan_result,
            )
            tax_after = run_tax_projection_autochain(
                gross_for_tax=gross_for_tax_after,
                execute_tool_call_fn=lambda name, args: _execute_tool_call(
                    name,
                    args,
                    request.client_id,
                    tool_db,
                    pension_portfolio=current_pension_portfolio,
                    force_max_exemption=False,
                    agent_reply=None,
                    user_approved=True,
                    request_id=req_id,
                ),
            )
            if tax_after is not None:
                yield (
                    "\n\n🔧 **פלט כלי (הערכת מס - אחרי קיבוע זכויות):**\n" + tax_after
                )
                history_messages.append(
                    ChatMessage(
                        role="system",
                        content=build_tax_result_system_message_for_stream(tax_after),
                    )
                )

            forced_fixation_chain_done = True

    return forced_fixation_chain_done
