from __future__ import annotations

from typing import Any

from app.services.agent_execution.policy import decide
from app.services.llm_chat.explicit_tool_shortcuts import (
    CLIENT_SNAPSHOT_TOOL_NAME,
    is_explicit_client_snapshot_request,
)
from app.guards.tool_intent_guard import (
    get_tools_disabled_reason,
    is_conceptual_no_execute_request,
    sanitize_words_only_conceptual,
)
from app.services.llm_chat.orchestration_utils_parts.guards_and_validations import (
    is_process_termination_request,
)
from app.services.llm_chat.intent_classifier import detect_intent
from app.services.llm_chat.orchestration_utils_parts.tool_names import (
    MONTHLY_PENSION_SUMMARY_TOOL_NAME,
    TERMINATION_CONCEPTUAL_NO_EXECUTE_REPLY_TOOL_NAME,
)

from app.services.llm_chat.capability_router.router_facade import (
    ensure_router_decision,
    maybe_emit_router_selected_trace,
)

from .canonicalize import canonicalize_tool_args
from .core_types import (
    DecisionCode,
    FeatureFlagKey,
    OrchestrationDecision,
    OrchestrationDeps,
    OrchestrationInput,
    PlanKind,
    TraceEventSpec,
)


_LAST_TOOL_RESULT_RESPOND_ONLY_TOOL_NAMES = frozenset(
    {
        "EXECUTION_ONLY",
        CLIENT_SNAPSHOT_TOOL_NAME,
        MONTHLY_PENSION_SUMMARY_TOOL_NAME,
        TERMINATION_CONCEPTUAL_NO_EXECUTE_REPLY_TOOL_NAME,
    }
)


def orchestrate(
    input: OrchestrationInput,
    deps: OrchestrationDeps,
) -> tuple[OrchestrationDecision, list[TraceEventSpec]]:
    trace_id = getattr(input, "trace_id", None)

    def _maybe_emit_core_final_response(
        decision: OrchestrationDecision,
        trace_specs: list[TraceEventSpec],
    ) -> None:
        if decision.decision_code not in {
            DecisionCode.RESPOND_ONLY,
            DecisionCode.BLOCKED,
            DecisionCode.NEED_APPROVAL,
            DecisionCode.NEED_USER_TARGET,
        }:
            return
        if not isinstance(decision.final_text, str) or not (decision.final_text or "").strip():
            return
        trace_specs.append(
            TraceEventSpec(
                event_type="core_final_response",
                trace_id=trace_id,
                payload={
                    "reply_preview": str(decision.final_text)[:500],
                },
            )
        )

    user_text = (input.user_text or "").strip()

    _router_selected_spec: TraceEventSpec | None = None
    try:
        _router_decision = ensure_router_decision(
            user_text=user_text,
            client_id=getattr(input, "client_id", None),
            trace_id=trace_id,
        )
        _router_selected_spec = maybe_emit_router_selected_trace(trace_id=trace_id, decision=_router_decision)
    except Exception:
        _router_selected_spec = None

    last_tool_name = None
    try:
        last_tool = getattr(input, "last_tool_result", None)
        if last_tool is not None:
            last_tool_name = getattr(last_tool, "tool_name", None)
    except Exception:
        last_tool_name = None

    if getattr(input, "last_tool_result", None) is not None:
        try:
            _raw = getattr(input.last_tool_result, "tool_result", None)
        except Exception:
            _raw = None

        if isinstance(_raw, str) and ("###UI_ACTION###" in _raw) and ("approval_request" in _raw):
            already_sent = False
            try:
                if isinstance(input.state_snapshot, dict):
                    already_sent = bool(input.state_snapshot.get("approval_request_already_sent", False))
            except Exception:
                already_sent = False

            final_text = _raw
            if already_sent:
                final_text = "נדרש אישור לפני הפעלת כלי. ממתין לאישור בחלונית."

            decision = OrchestrationDecision(
                decision_code=DecisionCode.RESPOND_ONLY,
                plan_kind=PlanKind.QA_ONLY,
                tool_name=None,
                tool_args=None,
                final_text=final_text,
                requires_user_approval=False,
                debug_meta={
                    "from_last_tool_result": True,
                    "last_tool_name": last_tool_name,
                    "approval_request_short_circuit": True,
                    "approval_request_already_sent": already_sent,
                },
            )
            trace_specs: list[TraceEventSpec] = []
            if _router_selected_spec is not None:
                trace_specs.append(_router_selected_spec)
            trace_specs.append(
                TraceEventSpec(
                    event_type="core_next_action_decided",
                    trace_id=trace_id,
                    payload={
                        "decision_code": decision.decision_code.value,
                        "plan_kind": decision.plan_kind.value,
                    },
                )
            )
            _maybe_emit_core_final_response(decision, trace_specs)
            return decision, trace_specs

        try:
            if isinstance(input.state_snapshot, dict) and last_tool_name in {
                "BUILD_TARGET_PENSION_PLAN",
                "RUN_RETIREMENT_CASHFLOW_ANALYSIS",
            }:
                gross_for_tax_raw = input.state_snapshot.get("tax_autochain_gross_monthly_pension")
                gross_for_tax = None
                try:
                    if gross_for_tax_raw is not None:
                        gross_for_tax = float(gross_for_tax_raw)
                except Exception:
                    gross_for_tax = None

                if gross_for_tax is not None and gross_for_tax > 0:
                    plan_kind = PlanKind.QA_ONLY
                    tool_name = "GET_TAX_PROJECTION"
                    defaults = deps.tool_defaults(tool_name) if callable(deps.tool_defaults) else None
                    tool_args = canonicalize_tool_args(
                        tool_name,
                        {"gross_monthly_pension": gross_for_tax},
                        defaults=defaults,
                    )
                    decision = OrchestrationDecision(
                        decision_code=DecisionCode.TOOL_CALL,
                        plan_kind=plan_kind,
                        tool_name=tool_name,
                        tool_args=tool_args,
                        final_text=None,
                        requires_user_approval=False,
                        debug_meta={
                            "tax_autochain": True,
                            "from_last_tool_result": True,
                            "last_tool_name": last_tool_name,
                        },
                    )
                    trace_specs: list[TraceEventSpec] = []
                    if _router_selected_spec is not None:
                        trace_specs.append(_router_selected_spec)
                    trace_specs.append(
                        TraceEventSpec(
                            event_type="core_next_action_decided",
                            trace_id=trace_id,
                            payload={
                                "decision_code": decision.decision_code.value,
                                "plan_kind": decision.plan_kind.value,
                                "tool_name": tool_name,
                            },
                        )
                    )
                    trace_specs.append(
                        TraceEventSpec(
                            event_type="core_tool_call",
                            trace_id=trace_id,
                            payload={
                                "tool_name": tool_name,
                                "tool_args": tool_args,
                            },
                        )
                    )
                    return decision, trace_specs
        except Exception:
            pass

    try:
        if isinstance(input.state_snapshot, dict) and bool(input.state_snapshot.get("forced_document_reply_stop")):
            forced_final = input.state_snapshot.get("forced_document_reply_final")
            if isinstance(forced_final, str) and forced_final.strip():
                decision = OrchestrationDecision(
                    decision_code=DecisionCode.RESPOND_ONLY,
                    plan_kind=PlanKind.QA_ONLY,
                    tool_name=None,
                    tool_args=None,
                    final_text=forced_final,
                    requires_user_approval=False,
                    debug_meta={
                        "forced_document_reply_short_circuit": True,
                    },
                )
                trace_specs: list[TraceEventSpec] = []
                if _router_selected_spec is not None:
                    trace_specs.append(_router_selected_spec)
                trace_specs.append(
                    TraceEventSpec(
                        event_type="core_next_action_decided",
                        trace_id=trace_id,
                        payload={
                            "decision_code": decision.decision_code.value,
                            "plan_kind": decision.plan_kind.value,
                        },
                    )
                )
                _maybe_emit_core_final_response(decision, trace_specs)
                return decision, trace_specs
    except Exception:
        pass

    if last_tool_name in _LAST_TOOL_RESULT_RESPOND_ONLY_TOOL_NAMES:
        final_text = ""
        try:
            raw_tool_result = getattr(input.last_tool_result, "tool_result", None)
            if isinstance(raw_tool_result, dict) and isinstance(raw_tool_result.get("reply"), str):
                final_text = raw_tool_result.get("reply") or ""
            elif isinstance(raw_tool_result, str):
                final_text = raw_tool_result
            else:
                final_text = str(raw_tool_result or "")
        except Exception:
            final_text = ""

        if not isinstance(final_text, str) or not final_text.strip():
            final_text = "Unable to produce response from tool execution."

        plan_kind = PlanKind.QA_ONLY
        decision = OrchestrationDecision(
            decision_code=DecisionCode.RESPOND_ONLY,
            plan_kind=plan_kind,
            tool_name=None,
            tool_args=None,
            final_text=final_text,
            requires_user_approval=False,
            debug_meta={"from_last_tool_result": True, "last_tool_name": last_tool_name},
        )
        trace_specs: list[TraceEventSpec] = []
        if _router_selected_spec is not None:
            trace_specs.append(_router_selected_spec)
        trace_specs.append(
            TraceEventSpec(
                event_type="core_next_action_decided",
                trace_id=trace_id,
                payload={
                    "decision_code": decision.decision_code.value,
                    "plan_kind": decision.plan_kind.value,
                },
            )
        )
        _maybe_emit_core_final_response(decision, trace_specs)
        return decision, trace_specs

    feature_flags: dict[FeatureFlagKey, bool] = {}
    try:
        feature_flags = dict(getattr(input, "feature_flags", {}) or {})
    except Exception:
        feature_flags = {}

    intent = detect_intent(user_text)

    tools_enabled = True
    executor_only = None
    if isinstance(input.state_snapshot, dict):
        tools_enabled = bool(input.state_snapshot.get("tools_enabled", True))
        executor_only = input.state_snapshot.get("executor_only")

    policy = None
    try:
        from app.schemas.llm_chat import ChatRequest

        _policy_request = ChatRequest(messages=[], client_id=input.client_id)
        if callable(getattr(deps, "policy_gate", None)):
            policy = deps.policy_gate(_policy_request, intent, allow_write=False)
        else:
            policy = decide(_policy_request, intent, allow_write=False)
    except Exception:
        policy = None

    execution_mode = "agent_mode"
    tools_allowed = True
    write_allowed = False
    if policy is not None:
        tools_allowed = bool(getattr(policy, "tools_allowed", True))
        write_allowed = bool(getattr(policy, "write_allowed", False))
        execution_mode = "agent_mode" if tools_allowed else "qa_mode"

    plan_kind = PlanKind.UNKNOWN
    decision = OrchestrationDecision(
        decision_code=DecisionCode.RESPOND_ONLY,
        plan_kind=plan_kind,
        tool_name=None,
        tool_args=None,
        final_text="",
        requires_user_approval=False,
        debug_meta={"legacy_fallback": True},
    )

    trace_specs: list[TraceEventSpec] = []
    if _router_selected_spec is not None:
        trace_specs.append(_router_selected_spec)
    trace_specs.append(
        TraceEventSpec(
            event_type="core_user_input",
            trace_id=trace_id,
            payload={
                "message_preview": user_text[:500],
                "executor_only": executor_only,
            },
        )
    )
    trace_specs.append(
        TraceEventSpec(
            event_type="core_intent_detected",
            trace_id=trace_id,
            payload={
                "chat_intent": getattr(intent, "value", str(intent)),
                "message_preview": user_text[:500],
            },
        )
    )
    trace_specs.append(
        TraceEventSpec(
            event_type="core_execution_mode_selected",
            trace_id=trace_id,
            payload={
                "execution_mode": execution_mode,
                "tools_allowed": bool(tools_allowed),
                "tools_enabled": bool(tools_enabled),
            },
        )
    )
    trace_specs.append(
        TraceEventSpec(
            event_type="core_policy_gate_result",
            trace_id=trace_id,
            payload={
                "tools_allowed": bool(tools_allowed),
                "write_allowed": bool(write_allowed),
            },
        )
    )

    if bool(feature_flags.get(FeatureFlagKey.EXEC_ONLY_PATH, False)) and (
        last_tool_name != "EXECUTION_ONLY"
    ):
        plan_kind = PlanKind.QA_ONLY
        tool_name = "EXECUTION_ONLY"
        defaults = deps.tool_defaults(tool_name) if callable(deps.tool_defaults) else None
        tool_args = canonicalize_tool_args(tool_name, {}, defaults=defaults)
        decision = OrchestrationDecision(
            decision_code=DecisionCode.TOOL_CALL,
            plan_kind=plan_kind,
            tool_name=tool_name,
            tool_args=tool_args,
            final_text=None,
            requires_user_approval=False,
            debug_meta=None,
        )
        if _router_selected_spec is not None and (not trace_specs or trace_specs[0] is not _router_selected_spec):
            trace_specs.insert(0, _router_selected_spec)
        trace_specs.append(
            TraceEventSpec(
                event_type="core_next_action_decided",
                trace_id=trace_id,
                payload={
                    "decision_code": decision.decision_code.value,
                    "plan_kind": decision.plan_kind.value,
                    "tool_name": tool_name,
                },
            )
        )
        trace_specs.append(
            TraceEventSpec(
                event_type="core_tool_call",
                trace_id=trace_id,
                payload={
                    "tool_name": tool_name,
                    "tool_args": tool_args,
                },
            )
        )
        return decision, trace_specs

    if bool(feature_flags.get(FeatureFlagKey.GREETING_SHORTCUT, False)):
        greeting = "שלום! נתחיל כך: אפשר לבקש ניתוח תיק, לבנות תכנית פרישה, או להפיק דוח מסכם."
        plan_kind = PlanKind.QA_ONLY
        decision = OrchestrationDecision(
            decision_code=DecisionCode.RESPOND_ONLY,
            plan_kind=plan_kind,
            tool_name=None,
            tool_args=None,
            final_text=greeting,
            requires_user_approval=False,
            debug_meta=None,
        )
        trace_specs.append(
            TraceEventSpec(
                event_type="core_next_action_decided",
                trace_id=trace_id,
                payload={
                    "decision_code": decision.decision_code.value,
                    "plan_kind": decision.plan_kind.value,
                },
            )
        )
        _maybe_emit_core_final_response(decision, trace_specs)
        return decision, trace_specs

    tools_disabled_reason = None
    try:
        tools_disabled_reason = get_tools_disabled_reason(user_text or "", intent)
    except Exception:
        tools_disabled_reason = None

    if (
        (not bool(executor_only))
        and bool(is_conceptual_no_execute_request(user_text))
        and tools_disabled_reason in {"conceptual", "conceptual_form"}
    ):
        if is_process_termination_request(user_text):
            plan_kind = PlanKind.QA_ONLY
            tool_name = TERMINATION_CONCEPTUAL_NO_EXECUTE_REPLY_TOOL_NAME
            defaults = deps.tool_defaults(tool_name) if callable(deps.tool_defaults) else None
            tool_args = canonicalize_tool_args(tool_name, {}, defaults=defaults)
            decision = OrchestrationDecision(
                decision_code=DecisionCode.TOOL_CALL,
                plan_kind=plan_kind,
                tool_name=tool_name,
                tool_args=tool_args,
                final_text=None,
                requires_user_approval=False,
                debug_meta=None,
            )
            if _router_selected_spec is not None and (not trace_specs or trace_specs[0] is not _router_selected_spec):
                trace_specs.insert(0, _router_selected_spec)
            trace_specs.append(
                TraceEventSpec(
                    event_type="core_tool_call",
                    trace_id=trace_id,
                    payload={
                        "tool_name": tool_name,
                        "tool_args": tool_args,
                    },
                )
            )
        else:
            reply = sanitize_words_only_conceptual("", user_text)
            plan_kind = PlanKind.QA_ONLY
            decision = OrchestrationDecision(
                decision_code=DecisionCode.RESPOND_ONLY,
                plan_kind=plan_kind,
                tool_name=None,
                tool_args=None,
                final_text=reply,
                requires_user_approval=False,
                debug_meta=None,
            )
        if _router_selected_spec is not None and (not trace_specs or trace_specs[0] is not _router_selected_spec):
            trace_specs.insert(0, _router_selected_spec)
        trace_specs.append(
            TraceEventSpec(
                event_type="core_next_action_decided",
                trace_id=trace_id,
                payload={
                    "decision_code": decision.decision_code.value,
                    "plan_kind": decision.plan_kind.value,
                },
            )
        )
        _maybe_emit_core_final_response(decision, trace_specs)
        return decision, trace_specs

    normalized = user_text
    lowered = normalized.lower()
    if (
        input.client_id is not None
        and (last_tool_name != MONTHLY_PENSION_SUMMARY_TOOL_NAME)
        and (
        (MONTHLY_PENSION_SUMMARY_TOOL_NAME.lower() in lowered)
        or ("monthly_pension" in lowered)
        or ("קצבה חודשית" in normalized)
        or ("קצבה נוכחית" in normalized)
        )
    ):
        plan_kind = PlanKind.QA_ONLY
        tool_name = MONTHLY_PENSION_SUMMARY_TOOL_NAME
        defaults = deps.tool_defaults(tool_name) if callable(deps.tool_defaults) else None
        tool_args = canonicalize_tool_args(tool_name, {}, defaults=defaults)
        decision = OrchestrationDecision(
            decision_code=DecisionCode.TOOL_CALL,
            plan_kind=plan_kind,
            tool_name=tool_name,
            tool_args=tool_args,
            final_text=None,
            requires_user_approval=False,
            debug_meta=None,
        )
        if _router_selected_spec is not None and (not trace_specs or trace_specs[0] is not _router_selected_spec):
            trace_specs.insert(0, _router_selected_spec)
        trace_specs.append(
            TraceEventSpec(
                event_type="core_next_action_decided",
                trace_id=input.trace_id,
                payload={
                    "decision_code": decision.decision_code.value,
                    "plan_kind": decision.plan_kind.value,
                    "tool_name": tool_name,
                },
            )
        )
        trace_specs.append(
            TraceEventSpec(
                event_type="core_tool_call",
                trace_id=input.trace_id,
                payload={
                    "tool_name": tool_name,
                    "tool_args": tool_args,
                },
            )
        )
        return decision, trace_specs

    if (
        input.client_id is not None
        and (last_tool_name != CLIENT_SNAPSHOT_TOOL_NAME)
        and is_explicit_client_snapshot_request(user_text)
    ):
        plan_kind = PlanKind.SYSTEM_SNAPSHOT
        tool_name = CLIENT_SNAPSHOT_TOOL_NAME
        defaults = deps.tool_defaults(tool_name) if callable(deps.tool_defaults) else None
        tool_args = canonicalize_tool_args(tool_name, {}, defaults=defaults)
        decision = OrchestrationDecision(
            decision_code=DecisionCode.TOOL_CALL,
            plan_kind=plan_kind,
            tool_name=tool_name,
            tool_args=tool_args,
            final_text=None,
            requires_user_approval=False,
            debug_meta=None,
        )
        if _router_selected_spec is not None and (not trace_specs or trace_specs[0] is not _router_selected_spec):
            trace_specs.insert(0, _router_selected_spec)
        trace_specs.append(
            TraceEventSpec(
                event_type="core_next_action_decided",
                trace_id=trace_id,
                payload={
                    "decision_code": decision.decision_code.value,
                    "plan_kind": decision.plan_kind.value,
                    "tool_name": tool_name,
                },
            )
        )
        trace_specs.append(
            TraceEventSpec(
                event_type="core_tool_call",
                trace_id=trace_id,
                payload={
                    "tool_name": tool_name,
                    "tool_args": tool_args,
                },
            )
        )
        return decision, trace_specs

    if _router_selected_spec is not None and (not trace_specs or trace_specs[0] is not _router_selected_spec):
        trace_specs.insert(0, _router_selected_spec)
    trace_specs.append(
        TraceEventSpec(
            event_type="core_next_action_decided",
            trace_id=trace_id,
            payload={
                "decision_code": decision.decision_code.value,
                "plan_kind": decision.plan_kind.value,
            },
        )
    )
    return decision, trace_specs
