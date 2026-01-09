from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.schemas.llm_chat import ChatMessage


@dataclass
class _PreparedOrchestrationInputs:
    messages: list[ChatMessage]
    original_user_msg: str | None
    current_pension_portfolio: Any
    computed_data: Any
    is_qa_mode: bool
    no_tools_requested: bool
    is_doc_request: bool
    is_cashflow_request: bool
    is_comparison_request: bool
    is_net_request: bool
    is_portfolio_analysis: bool
    analysis_default_retirement_age: int | None
    force_max_exemption: bool
    wants_ignore_blocked: bool
    explicit_termination: bool
    termination_change: bool
    termination_already_executed: bool
    wants_execute_target_plan: bool
    wants_fixation_execute: bool
