import re

from fastapi.responses import StreamingResponse


def _maybe_handle_post_conversion_lock_early_block(
    *,
    request,
    db,
    logger,
    stream_request_id: str,
    original_user_msg: str,
    wants_execute_target_plan: bool,
    explicit_transform: bool,
    is_transform_request,
    load_pending_approval_ui_action_if_match,
    build_post_conversion_lock_message,
    build_post_conversion_plan_message,
):
    if not (request.client_id is not None and isinstance(original_user_msg, str)):
        return None

    candidate = original_user_msg.strip()
    lowered = candidate.lower()

    if wants_execute_target_plan:
        return None

    wants_plan_build = ("תכנית" in candidate) or ("תוכנית" in candidate)
    has_numeric_target = False
    try:
        cleaned = candidate.replace(",", "")
        has_numeric_target = bool(re.search(r"\b\d{4,6}\b", cleaned))
    except Exception:
        has_numeric_target = False

    wants_direct_transform = bool(
        explicit_transform
        or is_transform_request(candidate)
        or ("transform" in lowered)
        or ("המר" in candidate)
        or ("המרה" in candidate)
    )

    if wants_direct_transform or (wants_plan_build and has_numeric_target):
        pending_execute_target_plan = False
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

        logger.info(
            "post_conversion_lock_early_block",
            extra={
                "endpoint": "stream",
                "request_id": stream_request_id,
                "client_id": request.client_id,
                "post_conversion_locked": True,
                "wants_execute_target_plan": bool(wants_execute_target_plan),
                "pending_execute_target_plan": bool(pending_execute_target_plan),
                "blocked_plan_build": bool(wants_plan_build and has_numeric_target),
                "blocked_direct_transform": bool(wants_direct_transform),
            },
        )

        # Never block a user request to build a target pension plan.
        if wants_plan_build and has_numeric_target:
            return None

        return StreamingResponse(
            iter([build_post_conversion_lock_message()]),
            media_type="text/plain",
        )

    return None


def _maybe_handle_post_conversion_lock_late_block(
    *,
    request,
    db,
    logger,
    stream_request_id: str,
    original_user_msg: str,
    wants_execute_target_plan: bool,
    explicit_transform: bool,
    is_transform_request,
    load_pending_approval_ui_action_if_match,
    build_post_conversion_lock_message,
    build_post_conversion_plan_message,
):
    if not (request.client_id is not None and isinstance(original_user_msg, str)):
        return None

    candidate = original_user_msg.strip()
    lowered = candidate.lower()

    wants_plan_build = ("תכנית" in candidate) or ("תוכנית" in candidate)
    has_numeric_target = False
    try:
        cleaned = candidate.replace(",", "")
        has_numeric_target = bool(re.search(r"\b\d{4,6}\b", cleaned))
    except Exception:
        has_numeric_target = False

    pending_execute_target_plan = False
    pending_execute_scenario = False
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

    logger.info(
        "post_conversion_lock_evaluation",
        extra={
            "endpoint": "stream",
            "request_id": stream_request_id,
            "client_id": request.client_id,
            "post_conversion_locked": True,
            "wants_execute_target_plan": bool(wants_execute_target_plan),
            "pending_execute_target_plan": bool(pending_execute_target_plan),
            "pending_execute_retirement_scenario": bool(pending_execute_scenario),
        },
    )

    wants_direct_transform = bool(
        explicit_transform
        or is_transform_request(candidate)
        or ("transform" in lowered)
        or ("המר" in candidate)
        or ("המרה" in candidate)
    )

    if wants_direct_transform:
        return StreamingResponse(
            iter([build_post_conversion_lock_message()]),
            media_type="text/plain",
        )

    # Never block a user request to build a target pension plan.
    if wants_plan_build and has_numeric_target and (not wants_execute_target_plan):
        return None

    return None
