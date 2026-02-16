from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.schemas.llm_chat import ChatRequest
from app.services.llm_chat.intent_classifier import ChatIntent


class ExecutionMode(str, Enum):
    NONE = "none"
    LLM_TOOL_ROUTED = "llm_tool_routed"
    DETERMINISTIC_TARGET_PLAN = "deterministic_target_plan"


@dataclass(frozen=True)
class PolicyDecision:
    mode: ExecutionMode
    tools_allowed: bool
    write_allowed: bool
    missing_params: list[str] = field(default_factory=list)


def decide(
    request: ChatRequest,
    intent: ChatIntent,
    allow_write: bool = False,
) -> PolicyDecision:
    """Pure policy gate.

    MUST:
    - Be deterministic.
    - Have no DB access / no side effects.
    - Make no tool calls.

    Current phase constraints:
    - allow_write is forced to False.
    - DETERMINISTIC_TARGET_PLAN exists but is not reachable yet.
    """

    _ = request

    write_allowed = False

    tools_allowed = intent != ChatIntent.NO_TOOLS

    return PolicyDecision(
        mode=ExecutionMode.LLM_TOOL_ROUTED,
        tools_allowed=bool(tools_allowed),
        write_allowed=write_allowed,
        missing_params=[],
    )
