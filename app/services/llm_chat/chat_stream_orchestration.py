import logging

from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.schemas.llm_chat import ChatMessage, ChatRequest
from app.services.agent_execution.tool_executor import execute_tool_call
from app.services.llm_pension_agent_service import pension_llm_service
from app.services.llm_chat.chat_orchestration_helpers import (
    build_transform_accounts_from_target_plan_payload,
    store_pending_approval_request,
)
from app.services.pension_portfolio.snapshot_loader import (
    load_latest_pension_portfolio_snapshot_models,
)
from app.services.llm_chat.chat_stream_orchestration_parts.orchestrator import (
    run_pension_chat_stream,
)

PC_LLM_MAX_RETRIES = 3
PC_LLM_TIMEOUT_SECONDS = 120.0
PC_LLM_BACKOFF_SECONDS = (0.75, 1.5, 3.0)

logger = logging.getLogger("app.llm_chat")

store_pending_approval_request = store_pending_approval_request
load_latest_pension_portfolio_snapshot_models = (
    load_latest_pension_portfolio_snapshot_models
)
build_transform_accounts_from_target_plan_payload = (
    build_transform_accounts_from_target_plan_payload
)

__all__ = [
    "run_pension_chat_stream",
    "execute_tool_call",
    "pension_llm_service",
    "store_pending_approval_request",
    "load_latest_pension_portfolio_snapshot_models",
    "build_transform_accounts_from_target_plan_payload",
    "PC_LLM_MAX_RETRIES",
    "PC_LLM_TIMEOUT_SECONDS",
    "PC_LLM_BACKOFF_SECONDS",
]
