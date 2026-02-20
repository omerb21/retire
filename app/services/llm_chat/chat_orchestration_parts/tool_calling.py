import importlib
import inspect
import logging
import uuid
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.utils.llm_chat_log import log_llm_event
from app.services.agent_trace_logger import log_trace_event as _log_agent_trace

logger = logging.getLogger("app.llm_chat")


def _get_chat_orchestration_facade():
    # NOTE: Must be dynamic import so that pytest monkeypatching
    # app.services.llm_chat.chat_orchestration continues to affect
    # runtime behavior even though logic lives in *_parts.
    return importlib.import_module("app.services.llm_chat.chat_orchestration")


def _get_execute_tool_call():
    facade = _get_chat_orchestration_facade()
    fn = getattr(facade, "execute_tool_call", None)
    if callable(fn):
        return fn
    from app.services.agent_execution.tool_executor import execute_tool_call as _local_execute_tool_call

    return _local_execute_tool_call


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

    tool_call_id = None
    try:
        tool_call_id = uuid.uuid4().hex
    except Exception:
        tool_call_id = None

    try:
        _log_agent_trace(
            event_type="tool_call",
            payload={
                "tool_name": tool_name,
                "tool_call_id": tool_call_id,
                "args_preview": str(args)[:200],
                "streaming": False,
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
    )
    result: str = ""
    try:
        execute_fn = _get_execute_tool_call()
        sig = inspect.signature(execute_fn)
        if "agent_reply" in sig.parameters or "user_approved" in sig.parameters:
            result = execute_fn(
                tool_name=tool_name,
                args=args,
                client_id=client_id,
                db=db,
                pension_portfolio=pension_portfolio,
                force_max_exemption=force_max_exemption,
                agent_reply=agent_reply,
                user_approved=user_approved,
            )
            _log_tool_result(tool_name, result, client_id, tool_call_id)
            return result
    except Exception:
        pass

    execute_fn = _get_execute_tool_call()
    result = execute_fn(
        tool_name=tool_name,
        args=args,
        client_id=client_id,
        db=db,
        pension_portfolio=pension_portfolio,
        force_max_exemption=force_max_exemption,
    )
    _log_tool_result(tool_name, result, client_id, tool_call_id)
    return result


def _log_tool_result(tool_name: str, result: str, client_id: int, tool_call_id: str | None) -> None:
    try:
        _log_agent_trace(
            event_type="tool_result",
            payload={
                "tool_name": tool_name,
                "tool_call_id": tool_call_id,
                "status": "ok",
                "success": True,
                "result_length": len(result or ""),
                "result_preview": (result or "")[:3000],
            },
            client_id=client_id,
        )
    except Exception:
        pass
