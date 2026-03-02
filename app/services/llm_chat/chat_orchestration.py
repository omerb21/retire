import logging

from app.services.agent_execution.tool_executor import execute_tool_call
from app.services.llm_chat.chat_orchestration_parts.orchestrator import (
    run_pension_chat,
    run_pension_chat_stream,
)
from app.services.llm_pension_agent_service import pension_llm_service
from app.services.pension_portfolio.snapshot_loader import (
    load_latest_pension_portfolio_snapshot_models,
)

logger = logging.getLogger("app.llm_chat")


def select_case(*, user_message: str | None, messages, client_id):
    from app.services.llm_chat.case_router import select_case as _select_case

    return _select_case(
        user_message=user_message, messages=messages, client_id=client_id
    )


__all__ = [
    "run_pension_chat",
    "run_pension_chat_stream",
    "select_case",
    "execute_tool_call",
    "pension_llm_service",
    "load_latest_pension_portfolio_snapshot_models",
]
