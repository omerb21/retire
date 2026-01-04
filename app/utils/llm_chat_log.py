"""
LLM Chat Logging Utility

Provides structured JSONL logging for LLM agent conversations, including:
- User messages
- Tool calls with arguments
- Tool results
- Final agent answers

All entries share a request_id for correlation.
"""
import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from contextvars import ContextVar
from typing import Any, Optional

logger = logging.getLogger(__name__)

_current_request_id: ContextVar[Optional[str]] = ContextVar("llm_request_id", default=None)
_current_case_id: ContextVar[Optional[str]] = ContextVar("llm_case_id", default=None)

# Maximum characters to log for large payloads (tool results, answers)
MAX_PAYLOAD_CHARS = 5000


def _ensure_logs_dir() -> Path:
    """Ensure logs directory exists and return its path."""
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    return logs_dir


def _truncate(text: str, max_chars: int = MAX_PAYLOAD_CHARS) -> str:
    """Truncate text if it exceeds max_chars, appending indicator."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"... [TRUNCATED, total {len(text)} chars]"


def generate_request_id() -> str:
    """Generate a unique request ID (UUID4) for a chat request."""
    return str(uuid.uuid4())


def set_current_request_id(request_id: Optional[str]) -> None:
    _current_request_id.set(request_id)


def set_current_case_id(case_id: Optional[str]) -> None:
    _current_case_id.set(case_id)


def get_current_request_id() -> Optional[str]:
    return _current_request_id.get()


def get_current_case_id() -> Optional[str]:
    return _current_case_id.get()


def log_llm_event(
    request_id: str,
    event_type: str,
    payload: Any,
    client_id: Optional[int] = None,
    extra: Optional[dict] = None,
) -> None:
    """
    Log an LLM chat event to logs/llm_chat.log in JSONL format.

    Args:
        request_id: Unique identifier for the request/conversation turn.
        event_type: One of 'user_message', 'tool_call', 'tool_result', 'final_answer', 'error'.
        payload: The main content (string or dict).
        client_id: Optional client ID for context.
        extra: Optional additional metadata.
    """
    logs_dir = _ensure_logs_dir()
    log_file = logs_dir / "llm_chat.log"

    # Prepare payload for logging
    if isinstance(payload, str):
        payload_to_log = _truncate(payload)
    elif isinstance(payload, dict):
        # Serialize dict, then truncate if needed
        payload_str = json.dumps(payload, ensure_ascii=False, default=str)
        payload_to_log = _truncate(payload_str)
    else:
        payload_to_log = _truncate(str(payload))

    entry = {
        "timestamp": datetime.now().isoformat(),
        "request_id": request_id,
        "event": event_type,
        "client_id": client_id,
        "payload": payload_to_log,
    }

    if extra:
        entry["extra"] = extra

    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    except Exception as e:
        # Don't let logging errors break the main application
        logger.warning("Warning: Failed to write LLM chat log: %s", e)
