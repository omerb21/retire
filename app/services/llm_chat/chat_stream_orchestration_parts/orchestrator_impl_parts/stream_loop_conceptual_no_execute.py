from fastapi.responses import StreamingResponse

from app.services.llm_chat.intent_classifier import detect_intent
from app.guards.tool_intent_guard import get_tools_disabled_reason
from app.services.llm_chat.orchestration_utils import is_process_termination_request
from app.guards.tool_intent_guard import sanitize_words_only_conceptual


def _maybe_handle_conceptual_no_execute_hard_stop(*, request, original_user_msg: str):
    # FLOW A: Conceptual-only hard stop must be early, before any deterministic tool/approval paths.
    # Apply ONLY when the user explicitly asked not to execute ("בלי לבצע" / "אל תבצע" etc),
    # to avoid breaking other conceptual-but-structured deterministic flows.
    if not (
        isinstance(original_user_msg, str)
        and original_user_msg
        and (not original_user_msg.startswith("###USER_APPROVED###"))
    ):
        return None

    from app.guards.tool_intent_guard import is_conceptual_no_execute_request

    if not is_conceptual_no_execute_request(original_user_msg):
        return None

    try:
        _intent_for_guard = detect_intent(original_user_msg)
        _disabled_reason = get_tools_disabled_reason(original_user_msg, _intent_for_guard)
    except Exception:
        _disabled_reason = None
    if _disabled_reason in {"conceptual", "conceptual_form"}:
        try:
            object.__setattr__(request, "tools_enabled", False)
            object.__setattr__(request, "tools_disabled_reason", _disabled_reason)
        except Exception:
            pass

        # Termination/compensation conceptual-no-execute requests must not return a generic
        # conceptual reply, because we want a termination-specific principle-only response
        # (without any execution-like language).
        if not is_process_termination_request(original_user_msg):
            conceptual_reply = sanitize_words_only_conceptual("", original_user_msg)
            return StreamingResponse(
                iter([conceptual_reply]),
                media_type="text/plain; charset=utf-8",
            )

    return None
