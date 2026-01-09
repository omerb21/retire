from __future__ import annotations


def _set_case_id_safe(original_user_msg, messages, client_id) -> None:
    import importlib

    try:
        case_router = importlib.import_module("app.services.llm_chat.case_router")
        select_case = getattr(case_router, "select_case", None)
        if callable(select_case):
            decision = select_case(
                user_message=original_user_msg,
                messages=messages,
                client_id=client_id,
            )
            case_id = getattr(decision, "case_id", None)
            from app.utils.llm_chat_log import set_current_case_id

            set_current_case_id(case_id or "interactive_readonly")
        else:
            from app.utils.llm_chat_log import set_current_case_id

            set_current_case_id("interactive_readonly")
    except Exception:
        from app.utils.llm_chat_log import set_current_case_id

        set_current_case_id("interactive_readonly")
