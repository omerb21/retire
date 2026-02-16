from __future__ import annotations

from contextvars import ContextVar

from app.schemas.llm_chat import ChatRequest
from app.services.agent_execution.policy import PolicyDecision
from app.services.intent_classifier import IntentType


_current_request: ContextVar[ChatRequest | None] = ContextVar("tool_exec_request", default=None)
_current_policy_decision: ContextVar[PolicyDecision | None] = ContextVar("tool_exec_policy_decision", default=None)
_current_intent_type: ContextVar[IntentType | None] = ContextVar("tool_exec_intent_type", default=None)
_current_streaming: ContextVar[bool] = ContextVar("tool_exec_streaming", default=False)


def set_tool_execution_context(
    *,
    request: ChatRequest | None,
    policy_decision: PolicyDecision | None,
    intent_type: IntentType | None,
    streaming: bool,
) -> None:
    _current_request.set(request)
    _current_policy_decision.set(policy_decision)
    _current_intent_type.set(intent_type)
    _current_streaming.set(bool(streaming))


def get_current_tool_execution_request() -> ChatRequest | None:
    return _current_request.get()


def get_current_tool_execution_policy_decision() -> PolicyDecision | None:
    return _current_policy_decision.get()


def get_current_tool_execution_intent_type() -> IntentType | None:
    return _current_intent_type.get()


def get_current_tool_execution_streaming() -> bool:
    return bool(_current_streaming.get())
