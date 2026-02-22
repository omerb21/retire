from __future__ import annotations


def normalize_requested_tool_id(tool_name: str | None) -> str | None:
    if tool_name is None:
        return None
    if not isinstance(tool_name, str):
        return None
    t = tool_name.strip()
    if not t:
        return None

    return t
