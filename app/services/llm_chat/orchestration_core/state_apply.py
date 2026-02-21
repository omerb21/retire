from __future__ import annotations

from typing import Any

from .core_types import ToolResultEnvelope


def apply_tool_result_to_state(
    state_snapshot: dict | None,
    last_tool_result: ToolResultEnvelope,
) -> dict | None:
    if state_snapshot is None:
        return None

    if not isinstance(state_snapshot, dict):
        return state_snapshot

    try:
        new_state = dict(state_snapshot)
    except Exception:
        return state_snapshot

    try:
        history = new_state.get("tool_result_history")
        if not isinstance(history, list):
            history = []

        history.append(
            {
                "tool_name": last_tool_result.tool_name,
                "tool_call_id": last_tool_result.tool_call_id,
                "status": last_tool_result.status,
            }
        )
        new_state["tool_result_history"] = history[-20:]
    except Exception:
        pass

    return new_state
