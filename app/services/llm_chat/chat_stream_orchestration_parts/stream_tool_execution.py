import inspect
import logging
import uuid
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.utils.llm_chat_log import log_llm_event
from app.services.agent_trace_logger import log_trace_event
from app.utils.trace_context import get_current_trace_id, set_current_trace_id

from app.services.agent_execution.tool_execution_context import mark_tool_ok_seen

from .stream_top_level_helpers import _get_stream_orchestration_facade

logger = logging.getLogger("app.llm_chat")


def _execute_tool_call(
    tool_name: str,
    args: dict,
    client_id: int,
    db: Session,
    pension_portfolio: Optional[list[Any]] = None,
    force_max_exemption: bool = False,
    agent_reply: str | None = None,
    user_approved: bool = False,
    request_id: str | None = None,
) -> str:
    logger.info("⚡ Executing Tool: %s with args: %s", tool_name, args)

    effective_trace_id = None
    try:
        effective_trace_id = get_current_trace_id()
    except Exception:
        effective_trace_id = None
    if not effective_trace_id:
        try:
            if db is not None and hasattr(db, "info") and isinstance(getattr(db, "info", None), dict):
                candidate = db.info.get("trace_id")
                if isinstance(candidate, str) and candidate.strip():
                    effective_trace_id = candidate.strip()
        except Exception:
            effective_trace_id = None
    if effective_trace_id:
        try:
            # Ensure ContextVar is set so downstream logging/helpers share the same trace.
            set_current_trace_id(effective_trace_id)
        except Exception:
            pass

    def _get_execute_tool_call():
        facade = _get_stream_orchestration_facade()
        fn = getattr(facade, "execute_tool_call", None)
        if callable(fn):
            return fn
        from app.services.agent_execution.tool_executor import execute_tool_call as _local_execute_tool_call

        return _local_execute_tool_call

    execute_tool_call_fn = _get_execute_tool_call()

    try:
        from app.services.agent_execution.tool_executor import execute_tool_call as _ssot_execute_tool_call

        is_ssot = execute_tool_call_fn is _ssot_execute_tool_call
    except Exception:
        is_ssot = False

    if not is_ssot:
        try:
            trace_id = effective_trace_id
            if trace_id:
                log_trace_event(
                    trace_id=trace_id,
                    event_type="tool_call",
                    payload={
                        "tool_name": tool_name,
                        "args_preview": str(args)[:200],
                        "streaming": True,
                    },
                    client_id=client_id,
                )
        except Exception:
            pass

    req_id = request_id or "unknown"
    log_llm_event(
        request_id=req_id,
        event_type="tool_execution",
        payload={
            "execution_id": str(uuid.uuid4()),
            "tool_name": tool_name,
            "args": args if isinstance(args, dict) else {},
        },
        client_id=client_id,
        extra={"endpoint": "stream"},
    )
    try:
        sig = inspect.signature(execute_tool_call_fn)
        if "agent_reply" in sig.parameters or "user_approved" in sig.parameters:
            res = execute_tool_call_fn(
                tool_name=tool_name,
                args=args,
                client_id=client_id,
                db=db,
                pension_portfolio=pension_portfolio,
                force_max_exemption=force_max_exemption,
                agent_reply=agent_reply,
                user_approved=user_approved,
            )
        else:
            res = execute_tool_call_fn(
                tool_name=tool_name,
                args=args,
                client_id=client_id,
                db=db,
                pension_portfolio=pension_portfolio,
                force_max_exemption=force_max_exemption,
            )
    except Exception as exc:
        if not is_ssot:
            try:
                trace_id = effective_trace_id
                if trace_id:
                    log_trace_event(
                        trace_id=trace_id,
                        event_type="tool_result",
                        payload={
                            "tool_name": tool_name,
                            "status": "error_safe",
                            "streaming": True,
                            "result_preview": f"{type(exc).__name__}: {exc}"[:200],
                        },
                        client_id=client_id,
                    )
            except Exception:
                pass
        raise

    try:
        mark_tool_ok_seen()
    except Exception:
        pass

    if not is_ssot:
        try:
            trace_id = effective_trace_id
            if trace_id:
                log_trace_event(
                    trace_id=trace_id,
                    event_type="tool_result",
                    payload={
                        "tool_name": tool_name,
                        "status": "ok",
                        "streaming": True,
                        "result_preview": (res or "")[:200] if isinstance(res, str) else str(res)[:200],
                    },
                    client_id=client_id,
                )
        except Exception:
            pass

    return res
