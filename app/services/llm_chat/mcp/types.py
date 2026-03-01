from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class MCPExecutionMode(str, Enum):
    NEW_CORE = "NEW_CORE"
    NO_TOOLS = "NO_TOOLS"
    TOOL_ALLOWED = "TOOL_ALLOWED"
    TOOL_BLOCKED = "TOOL_BLOCKED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    LEGACY_BLOCKED = "LEGACY_BLOCKED"


class MCPOutcomeFinal(str, Enum):
    NO_TOOLS = "NO_TOOLS"
    TOOL_ALLOWED = "TOOL_ALLOWED"
    TOOL_BLOCKED = "TOOL_BLOCKED"
    PENDING_APPROVAL = "PENDING_APPROVAL"


@dataclass(frozen=True)
class MCPDecision:
    execution_mode: MCPExecutionMode
    reason_code: str
    capability_id: str | None
    intent_tier: str
    intent_type: str | None

    policy_matrix_present: bool = False
    policy_matrix_version: str | None = None

    policy_allowed_execution_modes: list[str] | None = None
    policy_violation: bool = False
    policy_violation_reason: str | None = None

    guard_present: bool = False
    guard_outcome: str | None = None
    guard_error_code: str | None = None
    guard_approval_request_id: str | None = None

    outcome_final: MCPOutcomeFinal | None = None

    trace_summary_version: str | None = None
    trace_summary_emitted: bool = False
