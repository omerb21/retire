import re

from fastapi.responses import StreamingResponse


def _is_post_conversion_locked(*, effective_client_state) -> bool:
    if effective_client_state is None:
        return False
    try:
        return str(getattr(effective_client_state, "mode", "")).strip() == "POST_CONVERSION_LOCKED"
    except Exception:
        return False


def _should_show_post_conversion_messages(*, effective_client_state) -> bool:
    if not _is_post_conversion_locked(effective_client_state=effective_client_state):
        return False
    if effective_client_state is None:
        return False
    try:
        return bool(getattr(effective_client_state, "has_any_conversion_assets", False))
    except Exception:
        return False


def _build_post_conversion_lock_message() -> str:
    return (
        "כותרת: מצב תיק לאחר המרה\n\n"
        "המערכת מזהה שכבר בוצעו המרות בתיק (Post Conversion).\n"
        "כדי למנוע דריסה/כפל המרות, לא מבצעים שוב המרה על בסיס snapshot.\n\n"
        "מה אפשר לעשות עכשיו:\n"
        "- להפיק דוח מסכם\n"
        "- לבצע משיכה/פעולות נוספות על בסיס הנכסים שנוצרו\n"
        "- לבצע קיבוע זכויות אם נדרש\n\n"
        'אם רצית לבצע פעולה אחרת, כתוב במפורש: "דוח מסכם" / "משיכה מהנכסים" / "קיבוע זכויות".\n'
    )


def _build_post_conversion_plan_message() -> str:
    return (
        "כותרת: תכנית יעד\n\n"
        "המערכת תבנה תכנית יעד על בסיס מצב הנתונים הנוכחי במערכת.\n"
    )


def _maybe_handle_post_conversion_lock_early_cutoff(
    *,
    request,
    db,
    logger,
    stream_request_id: str,
    original_user_msg: str,
    effective_client_state,
    load_pending_approval_ui_action_if_match,
    is_transform_request,
) -> StreamingResponse | None:
    if not _should_show_post_conversion_messages(effective_client_state=effective_client_state):
        return None
    if not isinstance(original_user_msg, str):
        return None

    candidate = original_user_msg.strip()
    lowered = candidate.lower()

    wants_execute_target_plan_local = (
        ("בצע" in lowered)
        and ("תכנית" in lowered or "תוכנית" in lowered or "מתווה" in lowered)
    )

    pending_execute_target_plan = False
    pending_execute_scenario = False
    if request.client_id is not None:
        try:
            pending_execute_target_plan = bool(
                load_pending_approval_ui_action_if_match(
                    db=db,
                    client_id=request.client_id,
                    request_kind="execute_target_plan",
                    tool_name="TRANSFORM_FUNDS_TO_ASSETS",
                )
            )
        except Exception:
            pending_execute_target_plan = False

        try:
            pending_execute_scenario = bool(
                load_pending_approval_ui_action_if_match(
                    db=db,
                    client_id=request.client_id,
                    request_kind="execute_retirement_scenario",
                    tool_name="EXECUTE_RETIREMENT_SCENARIO",
                )
            )
        except Exception:
            pending_execute_scenario = False

    if wants_execute_target_plan_local:
        return None

    wants_plan_build = ("תכנית" in candidate) or ("תוכנית" in candidate)
    has_numeric_target = False
    try:
        cleaned = candidate.replace(",", "")
        has_numeric_target = bool(re.search(r"\b\d{4,6}\b", cleaned))
    except Exception:
        has_numeric_target = False

    wants_direct_transform = bool(
        is_transform_request(candidate)
        or ("transform" in lowered)
        or ("המר" in candidate)
        or ("המרה" in candidate)
    )

    if wants_direct_transform or (wants_plan_build and has_numeric_target):
        logger.info(
            "post_conversion_lock_early_cutoff",
            extra={
                "endpoint": "stream",
                "request_id": stream_request_id,
                "client_id": request.client_id,
                "post_conversion_locked": True,
                "wants_execute_target_plan": bool(wants_execute_target_plan_local),
                "pending_execute_target_plan": bool(pending_execute_target_plan),
                "pending_execute_retirement_scenario": bool(pending_execute_scenario),
            },
        )

        # Never block a user request to build a target pension plan.
        if wants_plan_build and has_numeric_target:
            return None

        return StreamingResponse(
            iter([_build_post_conversion_lock_message()]),
            media_type="text/plain",
        )

    return None
