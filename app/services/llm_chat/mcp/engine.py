from __future__ import annotations

import os
from dataclasses import asdict, replace

from app.services.llm_chat.capability_router.ssot_loader import (
    load_capability_map,
    load_mcp_policy_matrix,
)

from .decision import (
    POLICY_MAPPING_MISSING,
    POLICY_VIOLATION,
    SIDE_EFFECT_CLASS_MISSING,
)
from .types import MCPDecision, MCPExecutionMode, MCPOutcomeFinal


class MCPEngine:
    @staticmethod
    def _finalize_outcome_final(decision: MCPDecision) -> MCPDecision:
        # Stage F.0: canonical, deterministic outcome. Must not change execution_mode.
        # Step 1: tier hard rules
        if decision.intent_tier in {"NO_TOOLS", "REPORT"}:
            return MCPDecision(
                execution_mode=decision.execution_mode,
                reason_code=decision.reason_code,
                capability_id=decision.capability_id,
                intent_tier=decision.intent_tier,
                intent_type=decision.intent_type,
                policy_matrix_present=decision.policy_matrix_present,
                policy_matrix_version=decision.policy_matrix_version,
                policy_allowed_execution_modes=decision.policy_allowed_execution_modes,
                policy_violation=decision.policy_violation,
                policy_violation_reason=decision.policy_violation_reason,
                guard_present=decision.guard_present,
                guard_outcome=decision.guard_outcome,
                guard_error_code=decision.guard_error_code,
                guard_approval_request_id=decision.guard_approval_request_id,
                outcome_final=MCPOutcomeFinal.NO_TOOLS,
            )

        # Step 2: guard precedence
        if decision.guard_outcome == "BLOCK":
            base_final = MCPOutcomeFinal.TOOL_BLOCKED
        elif decision.guard_outcome == "PENDING":
            base_final = MCPOutcomeFinal.PENDING_APPROVAL
        else:
            # Step 3: map execution_mode -> canonical outcome
            try:
                base_final = MCPOutcomeFinal(decision.execution_mode.value)
            except Exception:
                base_final = MCPOutcomeFinal.TOOL_BLOCKED

        policy_violation = decision.policy_violation
        policy_violation_reason = decision.policy_violation_reason

        # Conservative metadata-only fallback indicator when execution_mode is not canonical
        # (execution_mode remains unchanged by requirement).
        if (
            base_final == MCPOutcomeFinal.TOOL_BLOCKED
            and decision.execution_mode.value
            not in {
                MCPOutcomeFinal.NO_TOOLS.value,
                MCPOutcomeFinal.TOOL_ALLOWED.value,
                MCPOutcomeFinal.TOOL_BLOCKED.value,
                MCPOutcomeFinal.PENDING_APPROVAL.value,
            }
        ):
            policy_violation = True
            if not (
                isinstance(policy_violation_reason, str)
                and policy_violation_reason.strip()
            ):
                policy_violation_reason = "OUTCOME_FINAL_FALLBACK"

        # Step F.0: capability gap closure (metadata only)
        if (
            isinstance(decision.capability_id, str)
            and decision.capability_id
            and decision.capability_id != "default_qa_v1"
            and base_final == MCPOutcomeFinal.NO_TOOLS
            and decision.intent_tier not in {"NO_TOOLS", "REPORT"}
        ):
            base_final = MCPOutcomeFinal.TOOL_BLOCKED
            policy_violation = True
            policy_violation_reason = "BEHAVIOR_NOT_ACTIVATED"

        return MCPDecision(
            execution_mode=decision.execution_mode,
            reason_code=decision.reason_code,
            capability_id=decision.capability_id,
            intent_tier=decision.intent_tier,
            intent_type=decision.intent_type,
            policy_matrix_present=decision.policy_matrix_present,
            policy_matrix_version=decision.policy_matrix_version,
            policy_allowed_execution_modes=decision.policy_allowed_execution_modes,
            policy_violation=policy_violation,
            policy_violation_reason=policy_violation_reason,
            guard_present=decision.guard_present,
            guard_outcome=decision.guard_outcome,
            guard_error_code=decision.guard_error_code,
            guard_approval_request_id=decision.guard_approval_request_id,
            outcome_final=base_final,
        )

    def evaluate(
        self,
        *,
        intent_tier: str,
        intent_type: str | None,
        router_decision=None,
        guard_result=None,
        had_new_core_entered: bool,
        legacy_requested: bool,
    ) -> MCPDecision:
        _ = (router_decision, guard_result)

        it = str(intent_tier or "")
        it = it if it.strip() else "UNKNOWN"

        cap_id = None
        try:
            if router_decision is not None:
                cap_id = getattr(router_decision, "capability_id", None)
                if cap_id is not None:
                    cap_id = str(cap_id) if str(cap_id).strip() else None
        except Exception:
            cap_id = None

        tools_enabled = None
        tools_disabled_reason = None
        try:
            if isinstance(guard_result, dict):
                tools_enabled = guard_result.get("tools_enabled")
                tools_disabled_reason = guard_result.get("tools_disabled_reason")
        except Exception:
            tools_enabled = None
            tools_disabled_reason = None

        if tools_enabled is None:
            base = MCPDecision(
                execution_mode=MCPExecutionMode.TOOL_BLOCKED,
                reason_code="guard_missing",
                capability_id=cap_id,
                intent_tier=it,
                intent_type=str(intent_type) if intent_type is not None else None,
            )
        elif legacy_requested:
            base = MCPDecision(
                execution_mode=MCPExecutionMode.LEGACY_BLOCKED,
                reason_code="legacy_requested",
                capability_id=cap_id,
                intent_tier=it,
                intent_type=str(intent_type) if intent_type is not None else None,
            )
        elif had_new_core_entered:
            base = MCPDecision(
                execution_mode=MCPExecutionMode.NEW_CORE,
                reason_code="new_core_entered",
                capability_id=cap_id,
                intent_tier=it,
                intent_type=str(intent_type) if intent_type is not None else None,
            )
        elif tools_enabled is False:
            rc = str(tools_disabled_reason or "tool_blocked")
            rc = rc if rc.strip() else "tool_blocked"
            base = MCPDecision(
                execution_mode=MCPExecutionMode.TOOL_BLOCKED,
                reason_code=rc,
                capability_id=cap_id,
                intent_tier=it,
                intent_type=str(intent_type) if intent_type is not None else None,
            )
        else:
            has_tool_chain = False
            try:
                if router_decision is not None:
                    tc = getattr(router_decision, "tool_chain", None)
                    has_tool_chain = isinstance(tc, list) and len(tc) > 0
            except Exception:
                has_tool_chain = False

            if has_tool_chain:
                base = MCPDecision(
                    execution_mode=MCPExecutionMode.TOOL_ALLOWED,
                    reason_code="router_tool_chain",
                    capability_id=cap_id,
                    intent_tier=it,
                    intent_type=str(intent_type) if intent_type is not None else None,
                )
            else:
                base = MCPDecision(
                    execution_mode=MCPExecutionMode.NO_TOOLS,
                    reason_code="router_no_tools",
                    capability_id=cap_id,
                    intent_tier=it,
                    intent_type=str(intent_type) if intent_type is not None else None,
                )

        overlay = self._with_policy_overlay(base)
        decision = self._enforce_policy_b1_if_enabled(overlay)
        with_guard = self._with_guard_metadata(decision, guard_result)
        finalized = self._finalize_outcome_final(with_guard)
        return replace(
            finalized,
            trace_summary_version="stageG_v1",
            trace_summary_emitted=False,
        )

    @staticmethod
    def _with_guard_metadata(decision: MCPDecision, guard_result) -> MCPDecision:
        if not isinstance(guard_result, dict):
            return decision

        outcome = guard_result.get("outcome")
        error_code = guard_result.get("error_code")
        approval_request_id = guard_result.get("approval_request_id")

        outcome_s = (
            outcome.strip() if isinstance(outcome, str) and outcome.strip() else None
        )
        error_s = (
            error_code.strip()
            if isinstance(error_code, str) and error_code.strip()
            else None
        )
        approval_s = (
            approval_request_id.strip()
            if isinstance(approval_request_id, str) and approval_request_id.strip()
            else None
        )

        return MCPDecision(
            execution_mode=decision.execution_mode,
            reason_code=decision.reason_code,
            capability_id=decision.capability_id,
            intent_tier=decision.intent_tier,
            intent_type=decision.intent_type,
            policy_matrix_present=decision.policy_matrix_present,
            policy_matrix_version=decision.policy_matrix_version,
            policy_allowed_execution_modes=decision.policy_allowed_execution_modes,
            policy_violation=decision.policy_violation,
            policy_violation_reason=decision.policy_violation_reason,
            guard_present=True,
            guard_outcome=outcome_s,
            guard_error_code=error_s,
            guard_approval_request_id=approval_s,
        )

    @staticmethod
    def _is_policy_enforcement_b1_enabled() -> bool:
        v = os.getenv("MCP_POLICY_ENFORCEMENT_B1")
        if not isinstance(v, str):
            return False
        v = v.strip().lower()
        return v in {"1", "true"}

    def _enforce_policy_b1_if_enabled(self, decision: MCPDecision) -> MCPDecision:
        if not self._is_policy_enforcement_b1_enabled():
            return decision

        allowed = decision.policy_allowed_execution_modes

        if (
            allowed is None
            and decision.policy_violation_reason == POLICY_MAPPING_MISSING
        ):
            # Transitional rule: when enforcement is enabled and the policy mapping
            # is missing, we signal violation but do not change runtime behavior.
            return MCPDecision(
                execution_mode=decision.execution_mode,
                reason_code=decision.reason_code,
                capability_id=decision.capability_id,
                intent_tier=decision.intent_tier,
                intent_type=decision.intent_type,
                policy_matrix_present=decision.policy_matrix_present,
                policy_matrix_version=decision.policy_matrix_version,
                policy_allowed_execution_modes=None,
                policy_violation=True,
                policy_violation_reason=POLICY_MAPPING_MISSING,
            )

        if not isinstance(allowed, list) or not allowed:
            return decision

        base_mode = decision.execution_mode.value
        if base_mode in allowed:
            return decision

        restrictiveness_rank: dict[str, int] = {
            "NO_TOOLS": 0,
            "TOOL_BLOCKED": 1,
            "PENDING_APPROVAL": 2,
            "TOOL_ALLOWED": 3,
        }
        downgrade_order = [
            "NO_TOOLS",
            "TOOL_BLOCKED",
            "PENDING_APPROVAL",
            "TOOL_ALLOWED",
        ]

        base_rank = restrictiveness_rank.get(base_mode)
        if base_rank is None:
            return decision

        chosen: str | None = None
        for candidate in downgrade_order:
            cand_rank = restrictiveness_rank.get(candidate)
            if cand_rank is None:
                continue
            if cand_rank > base_rank:
                continue
            if candidate in allowed:
                chosen = candidate
                break

        if chosen is None or chosen == base_mode:
            return decision

        try:
            chosen_enum = MCPExecutionMode(chosen)
        except Exception:
            return decision

        return MCPDecision(
            execution_mode=chosen_enum,
            reason_code=decision.reason_code,
            capability_id=decision.capability_id,
            intent_tier=decision.intent_tier,
            intent_type=decision.intent_type,
            policy_matrix_present=decision.policy_matrix_present,
            policy_matrix_version=decision.policy_matrix_version,
            policy_allowed_execution_modes=list(allowed),
            policy_violation=True,
            policy_violation_reason=POLICY_VIOLATION,
        )

    def _with_policy_overlay(self, base: MCPDecision) -> MCPDecision:
        """Stage B (fixed): policy validation overlay only.

        This computes allowed execution modes from the SSOT policy matrix and
        compares them against the existing decision.execution_mode.

        It MUST NOT change execution_mode.
        """

        try:
            matrix = load_mcp_policy_matrix()
        except Exception:
            matrix = None

        policy_matrix_present = isinstance(matrix, dict)
        version_s: str | None = None
        if policy_matrix_present:
            version = matrix.get("policy_matrix_version")
            version_s = (
                str(version).strip()
                if isinstance(version, str) and version.strip()
                else None
            )

        side_effect_class = self._resolve_side_effect_class(base.capability_id)
        if side_effect_class is None:
            return MCPDecision(
                execution_mode=base.execution_mode,
                reason_code=base.reason_code,
                capability_id=base.capability_id,
                intent_tier=base.intent_tier,
                intent_type=base.intent_type,
                policy_matrix_present=policy_matrix_present,
                policy_matrix_version=version_s,
                policy_allowed_execution_modes=None,
                policy_violation=False,
                policy_violation_reason=SIDE_EFFECT_CLASS_MISSING,
            )

        allowed = self._apply_policy_matrix(
            intent_tier=base.intent_tier,
            intent_type=base.intent_type,
            side_effect_class=side_effect_class,
        )

        if allowed is None:
            return MCPDecision(
                execution_mode=base.execution_mode,
                reason_code=base.reason_code,
                capability_id=base.capability_id,
                intent_tier=base.intent_tier,
                intent_type=base.intent_type,
                policy_matrix_present=policy_matrix_present,
                policy_matrix_version=version_s,
                policy_allowed_execution_modes=None,
                policy_violation=False,
                policy_violation_reason=POLICY_MAPPING_MISSING,
            )

        exec_mode_s = base.execution_mode.value
        is_allowed = exec_mode_s in allowed
        return MCPDecision(
            execution_mode=base.execution_mode,
            reason_code=base.reason_code,
            capability_id=base.capability_id,
            intent_tier=base.intent_tier,
            intent_type=base.intent_type,
            policy_matrix_present=policy_matrix_present,
            policy_matrix_version=version_s,
            policy_allowed_execution_modes=list(allowed),
            policy_violation=not is_allowed,
            policy_violation_reason=None if is_allowed else POLICY_VIOLATION,
        )

    @staticmethod
    def _resolve_side_effect_class(capability_id: str | None) -> str | None:
        if not (isinstance(capability_id, str) and capability_id.strip()):
            return None

        try:
            cap_map = load_capability_map()
        except Exception:
            return None

        caps_raw = cap_map.get("capabilities") if isinstance(cap_map, dict) else None
        caps = caps_raw if isinstance(caps_raw, list) else []

        for cap in caps:
            if not isinstance(cap, dict):
                continue
            if cap.get("capability_id") != capability_id:
                continue
            sec = cap.get("side_effect_class")
            if isinstance(sec, str) and sec.strip():
                return sec.strip()
            return None

        return None

    def _apply_policy_matrix(
        self,
        intent_tier: str,
        intent_type: str | None,
        side_effect_class: str,
    ) -> list[str] | None:
        """Return allowed execution modes from the SSOT policy matrix (or None).

        IMPORTANT: this does not choose execution_mode.
        """

        try:
            matrix = load_mcp_policy_matrix()
        except Exception:
            matrix = None

        if not isinstance(matrix, dict):
            return None

        entries_raw = matrix.get("entries")
        entries = entries_raw if isinstance(entries_raw, list) else []

        tier_s = str(intent_tier or "").strip()
        type_s = str(intent_type or "").strip()
        sec_s = str(side_effect_class or "").strip()
        if not (tier_s and type_s and sec_s):
            return None

        for e in entries:
            if not isinstance(e, dict):
                continue
            if str(e.get("intent_tier") or "").strip() != tier_s:
                continue
            if str(e.get("intent_type") or "").strip() != type_s:
                continue
            if str(e.get("side_effect_class") or "").strip() != sec_s:
                continue

            allowed_raw = e.get("allowed_execution_modes")
            if not isinstance(allowed_raw, list) or not allowed_raw:
                return None

            allowed: list[str] = []
            for m in allowed_raw:
                if isinstance(m, str) and m.strip():
                    allowed.append(m.strip())
            return allowed or None

        return None


def mcp_decision_to_payload(decision: MCPDecision) -> dict:
    d = asdict(decision)
    try:
        d["execution_mode"] = decision.execution_mode.value
    except Exception:
        pass
    try:
        if getattr(decision, "outcome_final", None) is not None:
            d["outcome_final"] = decision.outcome_final.value
    except Exception:
        pass
    return d
