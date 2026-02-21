from __future__ import annotations

from typing import Any

from .core_types import ToolResultEnvelope


def enrich_state_snapshot(
    state_snapshot: dict | None,
    *,
    user_text: str,
    last_tool_result: ToolResultEnvelope | None,
    facts: dict | None = None,
) -> dict | None:
    if state_snapshot is None:
        return None

    if not isinstance(state_snapshot, dict):
        return state_snapshot

    try:
        new_state: dict[str, Any] = dict(state_snapshot)
    except Exception:
        return state_snapshot

    if isinstance(facts, dict):
        try:
            for k, v in facts.items():
                new_state[k] = v
        except Exception:
            pass

    if (
        last_tool_result is not None
        and isinstance(last_tool_result.tool_name, str)
        and last_tool_result.tool_name
        in {
            "BUILD_TARGET_PENSION_PLAN",
            "RUN_RETIREMENT_CASHFLOW_ANALYSIS",
        }
    ):
        try:
            from app.services.llm_chat.chat_orchestration_helpers_parts.tax_autochain import (
                get_gross_for_tax_chaining,
            )
            from app.services.llm_chat.orchestration_utils_parts.guards_and_validations import (
                is_net_pension_request,
            )

            is_net = is_net_pension_request(user_text or "")
            gross_for_tax = get_gross_for_tax_chaining(
                is_net=is_net,
                tool_name=last_tool_result.tool_name,
                tool_result=str(getattr(last_tool_result, "tool_result", "") or ""),
            )
            if gross_for_tax is not None and gross_for_tax > 0:
                new_state["tax_autochain_gross_monthly_pension"] = float(gross_for_tax)
        except Exception:
            pass

    return new_state
