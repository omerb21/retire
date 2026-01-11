from app.services.llm_chat.message_utils import (
    extract_latest_approval_request,
    get_tool_call_approval_signature,
)
from app.utils.llm_chat_log import log_llm_event


def _stream_maybe_short_circuit_on_ui_action_approval_request(
    *,
    req_id: str,
    request,
    tool_name,
    tool_args,
    tool_result,
):
    if (
        isinstance(tool_result, str)
        and "###UI_ACTION###" in tool_result
        and "approval_request" in tool_result
    ):
        pending = extract_latest_approval_request(request.messages)
        if pending is not None:
            pending_tool, pending_args = pending
            pending_sig = get_tool_call_approval_signature(pending_tool, pending_args)
            current_sig = get_tool_call_approval_signature(
                tool_name, tool_args if isinstance(tool_args, dict) else {}
            )
            if pending_sig and current_sig and pending_sig == current_sig:
                log_llm_event(
                    request_id=req_id,
                    event_type="final_answer",
                    payload=(
                        "נדרש אישור לפני הפעלת כלי (כבר נשלחה בקשת אישור). ממתין לאישור בחלונית."
                    ),
                    client_id=request.client_id,
                    extra={"endpoint": "stream"},
                )
                yield "נדרש אישור לפני הפעלת כלי. ממתין לאישור בחלונית."
                return True

        log_llm_event(
            request_id=req_id,
            event_type="final_answer",
            payload=tool_result,
            client_id=request.client_id,
            extra={"endpoint": "stream"},
        )
        yield tool_result
        return True

    return False
