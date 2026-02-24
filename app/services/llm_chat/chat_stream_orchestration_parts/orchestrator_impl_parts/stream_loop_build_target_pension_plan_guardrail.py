from app.schemas.llm_chat import ChatMessage

from ..chat_helpers import (
    _extract_target_monthly_pension,
    _infer_target_is_net,
    _user_requested_target_pension_plan,
)


def _maybe_apply_build_target_pension_plan_guardrail(
    *,
    tool_name: str | None,
    tool_args,
    original_user_msg: str,
    history_messages: list[ChatMessage],
):
    if tool_name == "BUILD_TARGET_PENSION_PLAN":
        if not isinstance(tool_args, dict):
            tool_args = {}
        user_wants_plan = _user_requested_target_pension_plan(original_user_msg)
        raw_target = tool_args.get("target_monthly_pension")
        target_ok = False
        try:
            target_ok = float(raw_target or 0) > 0
        except Exception:
            target_ok = False

        if user_wants_plan:
            extracted_target = _extract_target_monthly_pension(original_user_msg)
            if extracted_target and extracted_target > 0:
                tool_args["target_monthly_pension"] = extracted_target
                try:
                    target_ok = float(extracted_target) > 0
                except Exception:
                    target_ok = False

            tool_args["target_is_net"] = _infer_target_is_net(original_user_msg)

        if (not user_wants_plan) or (not target_ok):
            history_messages.append(
                ChatMessage(
                    role="system",
                    content=(
                        "אזהרה: אסור לבצע BUILD_TARGET_PENSION_PLAN כאשר המשתמש ביקש ניתוח/אפשרויות משיכה בלבד, "
                        "או כאשר לא סופק יעד קצבה חודשי מספרי מפורש. "
                        "כעת אל תחזיר TOOL_CALL. במקום זאת: "
                        "(1) אם המשתמש ביקש ניתוח/אפשרויות משיכה – השב טקסטואלית על סמך טבלת המוצרים והחוקים; "
                        "(2) אם המשתמש מבקש תכנית יעד קצבה – שאל שאלה אחת: מה יעד הקצבה החודשי במספר (למשל 20000)."
                    ),
                )
            )
            return tool_args, True

    return tool_args, False
