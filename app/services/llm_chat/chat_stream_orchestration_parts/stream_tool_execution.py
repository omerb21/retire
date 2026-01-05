import inspect
import logging
import uuid
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.utils.llm_chat_log import log_llm_event

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

    execute_tool_call_fn = _get_stream_orchestration_facade().execute_tool_call

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
            return execute_tool_call_fn(
                tool_name=tool_name,
                args=args,
                client_id=client_id,
                db=db,
                pension_portfolio=pension_portfolio,
                force_max_exemption=force_max_exemption,
                agent_reply=agent_reply,
                user_approved=user_approved,
            )
    except Exception:
        pass

    return execute_tool_call_fn(
        tool_name=tool_name,
        args=args,
        client_id=client_id,
        db=db,
        pension_portfolio=pension_portfolio,
        force_max_exemption=force_max_exemption,
    )
