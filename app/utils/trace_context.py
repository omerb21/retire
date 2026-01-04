import uuid
from contextvars import ContextVar
from typing import Optional

_current_trace_id: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)


def generate_trace_id() -> str:
    return str(uuid.uuid4())


def set_current_trace_id(trace_id: Optional[str]) -> None:
    _current_trace_id.set(trace_id)


def get_current_trace_id() -> Optional[str]:
    return _current_trace_id.get()
