from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from datetime import date
from typing import Any, Callable, Optional


@dataclass(frozen=True)
class OrchestrationInput:
    user_text: str
    client_id: int | None
    session_id: str | None
    conversation_id: str | None
    feature_flags: dict["FeatureFlagKey", bool]
    request_meta: dict | None
    state_snapshot: dict | None
    last_tool_result: "ToolResultEnvelope | None" = None


@dataclass(frozen=True)
class ToolResultEnvelope:
    tool_name: str
    tool_args: dict
    tool_result: Any
    status: str  # "ok" | "error"
    error_message: str | None
    trace_id: str | None
    tool_call_id: str | None


class FeatureFlagKey(str, Enum):
    GREETING_SHORTCUT = "greeting_shortcut"
    EXEC_ONLY_PATH = "exec_only_path"


class DecisionCode(str, Enum):
    RESPOND_ONLY = "respond_only"
    TOOL_CALL = "tool_call"
    NEED_USER_TARGET = "need_user_target"
    BLOCKED = "blocked"
    NEED_APPROVAL = "need_approval"


class PlanKind(str, Enum):
    QA_ONLY = "qa_only"
    SYSTEM_SNAPSHOT = "system_snapshot"
    CASHFLOW = "cashflow"
    TARGET_PLAN = "target_plan"
    TERMINATION = "termination"
    FIXATION = "fixation"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class OrchestrationDecision:
    decision_code: DecisionCode
    plan_kind: PlanKind
    tool_name: str | None
    tool_args: dict | None
    final_text: str | None
    requires_user_approval: bool
    debug_meta: dict | None = None


@dataclass(frozen=True)
class TraceEventSpec:
    event_type: str
    payload: dict


@dataclass(frozen=True)
class OrchestrationDeps:
    llm_generate: Callable[[list[dict[str, Any]], Optional[int]], str]
    policy_gate: Callable[[Any], Any] | None = None
    intent_type_classifier: Callable[[], tuple[Any, Any]] | None = None
    get_today: Callable[[], date] | None = None
    tool_defaults: Callable[[str], dict] | None = None
