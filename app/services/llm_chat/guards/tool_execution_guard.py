from __future__ import annotations


def can_execute_tool(
    *,
    tool_name: str,
    request_kind: str | None,
    has_pending_approval: bool,
    user_intent: str | None,
) -> bool:
    if not isinstance(tool_name, str) or not tool_name.strip():
        return False

    tool = tool_name.strip().upper()
    intent = (user_intent or "").strip().lower()
    kind = (request_kind or "").strip().lower() or None

    if tool == "BUILD_TARGET_PENSION_PLAN":
        return kind in {"build_target_plan", "target_plan", "build"}

    if tool == "TRANSFORM_FUNDS_TO_ASSETS":
        if intent not in {"execute", "approve"}:
            return False
        return bool(has_pending_approval)

    if tool == "EXECUTE_RETIREMENT_SCENARIO":
        if intent not in {"execute", "approve"}:
            return False
        return bool(has_pending_approval)

    return bool(has_pending_approval)
