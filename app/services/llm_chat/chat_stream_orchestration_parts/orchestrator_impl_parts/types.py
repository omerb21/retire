from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.schemas.llm_chat import ChatMessage, ChatRequest


@dataclass
class StreamCtx:
    request: ChatRequest
    db: Session
    stream_request_id: str

    effective_portfolio: Any
    effective_snapshot_at: Any

    messages: list[ChatMessage]
    computed_data: Any
    original_user_msg: Optional[str]

    # flags / derived values
    is_net_request: bool = False
    is_doc_request: bool = False
    is_tax_doc_request: bool = False
    is_qa_mode: bool = False
    no_tools_requested: bool = False
    force_max_exemption: bool = False
    commutation_intent: bool = False
    explicit_transform: bool = False
    explicit_termination: bool = False
    termination_change: bool = False
    is_cashflow_request: bool = False
    is_comparison_request: bool = False
    is_portfolio_analysis: bool = False

    lowered_user_msg: str = ""
    wants_capital_transform: bool = False
    wants_execute_target_plan: bool = False
    wants_fixation_execute: bool = False
    wants_fixation_documents: bool = False
    explicit_cashflow_request: bool = False
    wants_cashflow_refresh: bool = False
    max_capital_request: bool = False
    wants_execute_max_capital: bool = False

    analysis_default_retirement_age: int | None = None
    termination_already_executed: bool = False

    wants_ignore_blocked: bool = False
