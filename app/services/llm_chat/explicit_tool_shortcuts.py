"""
Explicit tool shortcuts – deterministic tool execution without LLM.

Provides detection and execution helpers for cases where the user
explicitly names a tool (e.g. ``GET_CLIENT_SNAPSHOT``) and expects
the raw tool output, optionally as clean JSON only.

These helpers are intentionally free of any Router imports so they
can be used safely from deep orchestration layers without circular
dependencies.
"""

import json
import re
from typing import Optional

from sqlalchemy.orm import Session

CLIENT_SNAPSHOT_TOOL_NAME = "GET_CLIENT_SNAPSHOT"

_EXPLICIT_SNAPSHOT_RE = re.compile(rf"\b{CLIENT_SNAPSHOT_TOOL_NAME}\b", re.IGNORECASE)

_JSON_ONLY_PHRASES = (
    "רק json",
    "json בלבד",
    "בלי הסברים",
    "json only",
    "only json",
)


def is_explicit_client_snapshot_request(text: str) -> bool:
    """Return *True* if *text* explicitly mentions GET_CLIENT_SNAPSHOT."""
    return bool(_EXPLICIT_SNAPSHOT_RE.search(text or ""))


def wants_json_only(text: str) -> bool:
    """Return *True* if the user asked for JSON-only / no explanations."""
    lowered = (text or "").lower()
    return any(p in lowered for p in _JSON_ONLY_PHRASES)


def extract_first_json(text: str) -> Optional[str]:
    """Extract the first balanced ``{ … }`` JSON block from *text*.

    Returns the JSON string if it parses successfully, else ``None``.
    """
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start : i + 1]
                try:
                    json.loads(candidate)
                    return candidate
                except (json.JSONDecodeError, ValueError):
                    return None
    return None


def build_client_snapshot_tool_result(
    *, client_id: int, db: Session
) -> dict:
    """Execute GET_CLIENT_SNAPSHOT deterministically (no LLM) and return
    the parsed result dict.

    The returned dict always contains at least ``tool_name`` and
    ``success``.
    """
    from app.services.llm_chat.tool_handlers.get_client_snapshot import (
        handle_get_client_snapshot,
    )

    raw = handle_get_client_snapshot(args={}, client_id=client_id, db=db)
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {
            "tool_name": CLIENT_SNAPSHOT_TOOL_NAME,
            "success": False,
            "error": "Failed to parse tool output",
            "raw": (raw or "")[:2000],
        }
