from __future__ import annotations

import time
import json

import hashlib

import os

import inspect
import uuid

from sqlalchemy.orm import Session

from app.schemas.llm_chat import ChatRequest
from app.services.agent_execution.guard import build_blocked_tool_result, run_pre_tool_guard
from app.services.agent_execution.policy import PolicyDecision
from app.services.agent_execution.tool_contracts import (
    get_tool_contract,
    validate_tool_args,
    validate_tool_result,
)
from app.services.agent_execution.tool_execution_context import (
    get_current_tool_execution_intent_type,
    get_current_tool_execution_policy_decision,
    get_current_tool_execution_request,
    get_current_tool_execution_streaming,
    mark_tool_ok_seen,
)
from app.services.agent_trace_logger import log_trace_event
from app.services.intent_classifier import IntentType


def execute_with_guard(
    *,
    request: ChatRequest,
    db: Session,
    tool_name: str,
    tool_call_id: str | None = None,
    tool_args: dict,
    streaming: bool,
    policy_decision: PolicyDecision | None,
    intent_type: IntentType | None,
    pension_portfolio=None,
    force_max_exemption: bool = False,
    agent_reply: str | None = None,
    user_approved: bool = False,
    request_id: str | None = None,
) -> object:
    effective_trace_id = None
    try:
        effective_trace_id = getattr(request, "trace_id", None)
    except Exception:
        effective_trace_id = None
    if not effective_trace_id:
        try:
            from app.utils.trace_context import get_current_trace_id

            effective_trace_id = get_current_trace_id()
        except Exception:
            effective_trace_id = None

    if not effective_trace_id:
        try:
            if db is not None and hasattr(db, "info") and isinstance(getattr(db, "info", None), dict):
                candidate = db.info.get("trace_id")
                if isinstance(candidate, str) and candidate.strip():
                    effective_trace_id = candidate.strip()
        except Exception:
            effective_trace_id = None

    def _router_policy_gate_blocked_json(
        *,
        policy_reasons: list[str],
        detected_capability_id: str,
        mode: str,
    ) -> dict:
        return {
            "mode": mode,
            "status": "policy_blocked",
            "detected_capability_id": detected_capability_id,
            "what_ran": [],
            "missing_fields": [],
            "next_step": "adjust_request",
            "policy_reasons": list(policy_reasons),
        }

    _cap_router_policy_gate_enabled = False
    try:
        _cap_router_policy_gate_enabled = (os.getenv("CAPABILITY_ROUTER_POLICY_GATE_ENABLED") or "").strip() == "1"
    except Exception:
        _cap_router_policy_gate_enabled = False

    if _cap_router_policy_gate_enabled:
        try:
            from app.services.llm_chat.capability_router.runtime_context import get_router_decision
            from app.services.llm_chat.capability_router.tool_id_mapping import normalize_requested_tool_id

            router_decision = get_router_decision(trace_id=effective_trace_id)
            if router_decision is not None:
                requested_tool_id = normalize_requested_tool_id(tool_name)
                allowlist = set(router_decision.tool_chain or [])

                policy_reasons: list[str] = []
                if policy_decision is not None and (not bool(getattr(policy_decision, "tools_allowed", True))):
                    policy_reasons.append("qa_mode_no_tools")
                elif router_decision.mode == "QA":
                    policy_reasons.append("qa_mode_no_tools")
                elif (not requested_tool_id) or (requested_tool_id not in allowlist):
                    policy_reasons.append("tool_not_in_allowlist")

                if policy_reasons:
                    args_hash_fallback = False
                    try:
                        args_json = json.dumps(
                            tool_args if isinstance(tool_args, dict) else {},
                            sort_keys=True,
                            separators=(",", ":"),
                            ensure_ascii=False,
                        )
                        args_hash = hashlib.sha256(args_json.encode("utf-8")).hexdigest()
                    except Exception:
                        args_hash_fallback = True
                        args_hash = hashlib.sha256(b"").hexdigest()

                    try:
                        log_trace_event(
                            trace_id=effective_trace_id,
                            event_type="policy_gate_blocked",
                            payload={
                                "tool_id": str(requested_tool_id or tool_name or ""),
                                "args_hash": str(args_hash),
                                "args_hash_fallback": bool(args_hash_fallback),
                            },
                            client_id=request.client_id,
                        )
                    except Exception:
                        pass

                    return _router_policy_gate_blocked_json(
                        policy_reasons=policy_reasons,
                        detected_capability_id=router_decision.capability_id,
                        mode=str(router_decision.mode or "ACTION"),
                    )
        except Exception:
            pass

    def _log_event(*, event_type: str, payload: object, client_id: int | None) -> None:
        try:
            if effective_trace_id:
                try:
                    sig = inspect.signature(log_trace_event)
                    params = sig.parameters
                    supports_kwargs = any(
                        p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()
                    )
                    if supports_kwargs or ("trace_id" in params):
                        log_trace_event(
                            trace_id=effective_trace_id,
                            event_type=event_type,
                            payload=payload,
                            client_id=client_id,
                        )
                        return
                except Exception:
                    pass

            log_trace_event(event_type=event_type, payload=payload, client_id=client_id)
        except Exception:
            pass

    def _get_detected_capability_id_and_mode() -> tuple[str, str]:
        detected_capability_id = "budget_guard_unenforceable"
        mode = "ACTION"
        try:
            from app.services.llm_chat.capability_router.runtime_context import get_router_decision

            router_decision = get_router_decision(trace_id=effective_trace_id)
            if router_decision is not None:
                detected_capability_id = str(router_decision.capability_id or detected_capability_id)
                mode = str(router_decision.mode or mode)
        except Exception:
            pass
        return detected_capability_id, mode

    def _build_partial_result(*, status: str) -> dict:
        detected_capability_id, mode = _get_detected_capability_id_and_mode()
        return {
            "mode": mode,
            "status": str(status),
            "detected_capability_id": detected_capability_id,
            "what_ran": [],
            "missing_fields": [],
            "next_step": "contact_support",
        }

    def _emit_partial_returned(*, status: str, detected_capability_id: str) -> None:
        payload: dict[str, object] = {"status": str(status)}
        if detected_capability_id:
            payload["detected_capability_id"] = str(detected_capability_id)
        _log_event(event_type="partial_returned", payload=payload, client_id=request.client_id)

    try:
        max_tool_calls_env = os.getenv("CAP_ROUTER_MAX_TOOL_CALLS")
    except Exception:
        max_tool_calls_env = None

    if isinstance(max_tool_calls_env, str) and max_tool_calls_env.strip():
        _log_event(
            event_type="budget_guard_unenforceable",
            payload={"guard": "max_tool_calls", "mode": "per_tool"},
            client_id=request.client_id,
        )
        blocked_json = _build_partial_result(status="budget_config_invalid")
        _emit_partial_returned(
            status=str(blocked_json.get("status") or "budget_config_invalid"),
            detected_capability_id=str(blocked_json.get("detected_capability_id") or ""),
        )
        return blocked_json

    try:
        max_wall_clock_env = os.getenv("CAP_ROUTER_MAX_WALL_CLOCK_MS")
    except Exception:
        max_wall_clock_env = None

    if isinstance(max_wall_clock_env, str) and max_wall_clock_env.strip():
        _log_event(
            event_type="budget_guard_unenforceable",
            payload={"guard": "max_wall_clock_ms", "reason": "no_request_start_time"},
            client_id=request.client_id,
        )
        blocked_json = _build_partial_result(status="budget_config_invalid")
        _emit_partial_returned(
            status=str(blocked_json.get("status") or "budget_config_invalid"),
            detected_capability_id=str(blocked_json.get("detected_capability_id") or ""),
        )
        return blocked_json

    def _safe_args_preview(args_obj: object) -> str:
        try:
            if isinstance(args_obj, dict):
                return json.dumps(args_obj, sort_keys=True, ensure_ascii=False, default=str)[:200]
            return str(args_obj)[:200]
        except Exception:
            return "<unavailable>"

    def _safe_result_preview(res_obj: object) -> str:
        try:
            if res_obj is None:
                return ""
            if isinstance(res_obj, str):
                return res_obj[:200]
            if isinstance(res_obj, dict):
                return json.dumps(res_obj, sort_keys=True, ensure_ascii=False, default=str)[:200]
            return str(res_obj)[:200]
        except Exception:
            return "<unavailable>"

    tool_result_emitted = False
    call_payload = {
        "tool_name": tool_name,
        "tool_call_id": tool_call_id,
        "intent_type": getattr(intent_type, "value", None) if intent_type is not None else None,
        "args_preview": _safe_args_preview(tool_args),
        "streaming": bool(streaming),
    }
    if request_id is not None:
        call_payload["request_id"] = request_id
    _log_event(event_type="tool_call", payload=call_payload, client_id=request.client_id)

    guard_res = run_pre_tool_guard(
        request=request,
        db=db,
        tool_name=tool_name,
        tool_args=tool_args if isinstance(tool_args, dict) else {},
        policy_decision=policy_decision,
        intent_type=intent_type,
        user_approved=user_approved,
    )

    if not guard_res.ok:
        payload = {
            "tool_name": tool_name,
            "error_code": guard_res.error_code,
            "message": guard_res.message,
            "details": guard_res.details or {},
            "streaming": bool(streaming),
            "intent_type": getattr(intent_type, "value", None) if intent_type is not None else None,
        }
        _log_event(event_type="validation_error", payload=payload, client_id=request.client_id)

        blocked_json = build_blocked_tool_result(
            tool_name=tool_name,
            error_code=str(guard_res.error_code or "VALIDATION_ERROR"),
            message=str(guard_res.message or "Blocked by guard."),
            details=guard_res.details or {},
        )

        result_payload = {
            "tool_name": tool_name,
            "tool_call_id": tool_call_id,
            "status": "blocked_by_guard",
            "success": False,
            "intent_type": getattr(intent_type, "value", None) if intent_type is not None else None,
            "result_preview": _safe_result_preview(blocked_json),
            "streaming": bool(streaming),
        }
        if request_id is not None:
            result_payload["request_id"] = request_id
        _log_event(event_type="tool_result", payload=result_payload, client_id=request.client_id)
        tool_result_emitted = True

        return blocked_json

    contract = None
    try:
        contract = get_tool_contract(tool_name)
    except Exception:
        contract = None

    if contract is None:
        _log_event(
            event_type="tool_contract_missing",
            payload={
                "tool_name": tool_name,
                "streaming": bool(streaming),
                "intent_type": getattr(intent_type, "value", None) if intent_type is not None else None,
            },
            client_id=request.client_id,
        )
    else:
        ok_args, args_error = validate_tool_args(tool_name, tool_args)
        if not ok_args:
            try:
                try:
                    args_preview = str(tool_args)[:500]
                except Exception:
                    args_preview = "<unavailable>"

                _log_event(
                    event_type="tool_contract_violation",
                    payload={
                        "tool_name": tool_name,
                        "phase": "args",
                        "reason": args_error,
                        "args_preview": args_preview,
                        "streaming": bool(streaming),
                        "intent_type": getattr(intent_type, "value", None) if intent_type is not None else None,
                    },
                    client_id=request.client_id,
                )
            except Exception:
                pass

            detected_capability_id = "unknown"
            try:
                if _cap_router_policy_gate_enabled:
                    from app.services.llm_chat.capability_router.runtime_context import get_router_decision

                    router_decision = get_router_decision(trace_id=effective_trace_id)
                    if router_decision is not None:
                        detected_capability_id = str(router_decision.capability_id or detected_capability_id)
            except Exception:
                detected_capability_id = detected_capability_id

            blocked_json = {
                "mode": "ACTION",
                "status": "schema_error",
                "detected_capability_id": detected_capability_id,
                "what_ran": [tool_name],
                "missing_fields": [],
                "next_step": "adjust_request",
            }

            result_payload = {
                "tool_name": tool_name,
                "tool_call_id": tool_call_id,
                "status": "blocked_by_contract",
                "success": False,
                "intent_type": getattr(intent_type, "value", None) if intent_type is not None else None,
                "result_preview": _safe_result_preview(blocked_json),
                "streaming": bool(streaming),
            }
            if request_id is not None:
                result_payload["request_id"] = request_id
            _log_event(event_type="tool_result", payload=result_payload, client_id=request.client_id)
            tool_result_emitted = True

            return blocked_json

        _log_event(
            event_type="tool_contract_checked",
            payload={
                "tool_name": tool_name,
                "checked": True,
                "streaming": bool(streaming),
                "intent_type": getattr(intent_type, "value", None) if intent_type is not None else None,
            },
            client_id=request.client_id,
        )

    from app.services.llm_chat.tool_execution import execute_tool_call as _execute_tool_call_impl

    _supports_tool_call_id = False
    try:
        _supports_tool_call_id = ("tool_call_id" in inspect.signature(_execute_tool_call_impl).parameters)
    except Exception:
        _supports_tool_call_id = False

    try:
        from app.services.llm_chat.capability_router.tool_id_mapping import normalize_requested_tool_id

        _tool_id = str(normalize_requested_tool_id(tool_name) or tool_name or "")
        _args_hash: str
        try:
            _args_json = json.dumps(
                tool_args if isinstance(tool_args, dict) else {},
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            )
            _args_hash = hashlib.sha256(_args_json.encode("utf-8")).hexdigest()
        except Exception:
            _args_hash = hashlib.sha256(b"").hexdigest()

        _tool_start_mono = time.monotonic()
        _log_event(
            event_type="tool_started",
            payload={
                "tool_id": _tool_id,
                "args_hash": str(_args_hash),
            },
            client_id=request.client_id,
        )

        _exec_kwargs = {
            "tool_name": tool_name,
            "args": tool_args if isinstance(tool_args, dict) else {},
            "client_id": int(request.client_id) if request.client_id is not None else 0,
            "db": db,
            "pension_portfolio": pension_portfolio,
            "force_max_exemption": force_max_exemption,
            "agent_reply": agent_reply,
            "user_approved": user_approved,
        }
        if _supports_tool_call_id:
            _exec_kwargs["tool_call_id"] = tool_call_id
        tool_result = _execute_tool_call_impl(**_exec_kwargs)

        _duration_ms = int((time.monotonic() - _tool_start_mono) * 1000)
        _log_event(
            event_type="tool_finished",
            payload={
                "tool_id": _tool_id,
                "success": True,
                "duration_ms": int(_duration_ms),
            },
            client_id=request.client_id,
        )
    except Exception as exc:
        try:
            _duration_ms = 0
            try:
                _duration_ms = int((time.monotonic() - _tool_start_mono) * 1000)
            except Exception:
                _duration_ms = 0

            _log_event(
                event_type="tool_finished",
                payload={
                    "tool_id": _tool_id,
                    "success": False,
                    "duration_ms": int(_duration_ms),
                    "error_type": type(exc).__name__,
                },
                client_id=request.client_id,
            )
        except Exception:
            pass

        result_payload = {
            "tool_name": tool_name,
            "tool_call_id": tool_call_id,
            "status": "error_safe",
            "success": False,
            "intent_type": getattr(intent_type, "value", None) if intent_type is not None else None,
            "result_preview": _safe_result_preview(f"{type(exc).__name__}: {exc}"),
            "streaming": bool(streaming),
        }
        if request_id is not None:
            result_payload["request_id"] = request_id
        _log_event(event_type="tool_result", payload=result_payload, client_id=request.client_id)
        tool_result_emitted = True
        raise

    if contract is not None and contract.result_model is not None:
        ok_res, res_error = validate_tool_result(tool_name, tool_result)
        if not ok_res:
            try:
                try:
                    res_preview = (tool_result or "")[:500] if isinstance(tool_result, str) else str(tool_result)[:500]
                except Exception:
                    res_preview = "<unavailable>"

                _log_event(
                    event_type="tool_contract_violation",
                    payload={
                        "tool_name": tool_name,
                        "phase": "result",
                        "reason": res_error,
                        "result_preview": res_preview,
                        "streaming": bool(streaming),
                        "intent_type": getattr(intent_type, "value", None) if intent_type is not None else None,
                    },
                    client_id=request.client_id,
                )
            except Exception:
                pass

            detected_capability_id = "unknown"
            try:
                if _cap_router_policy_gate_enabled:
                    from app.services.llm_chat.capability_router.runtime_context import get_router_decision

                    router_decision = get_router_decision(trace_id=effective_trace_id)
                    if router_decision is not None:
                        detected_capability_id = str(router_decision.capability_id or detected_capability_id)
            except Exception:
                detected_capability_id = detected_capability_id

            blocked_json = {
                "mode": "ACTION",
                "status": "schema_error",
                "detected_capability_id": detected_capability_id,
                "what_ran": [tool_name],
                "missing_fields": [],
                "next_step": "adjust_request",
            }

            try:
                result_payload = {
                    "tool_name": tool_name,
                    "tool_call_id": tool_call_id,
                    "status": "blocked_by_contract",
                    "success": False,
                    "intent_type": getattr(intent_type, "value", None) if intent_type is not None else None,
                    "result_preview": _safe_result_preview(blocked_json),
                    "streaming": bool(streaming),
                }
                if request_id is not None:
                    result_payload["request_id"] = request_id
                _log_event(event_type="tool_result", payload=result_payload, client_id=request.client_id)
                tool_result_emitted = True
            except Exception:
                pass

            return blocked_json

    if not tool_result_emitted:
        try:
            mark_tool_ok_seen()
        except Exception:
            pass
        result_payload = {
            "tool_name": tool_name,
            "tool_call_id": tool_call_id,
            "status": "ok",
            "success": True,
            "contract_missing": bool(contract is None),
            "intent_type": getattr(intent_type, "value", None) if intent_type is not None else None,
            "result_preview": _safe_result_preview(tool_result),
            "streaming": bool(streaming),
        }
        if request_id is not None:
            result_payload["request_id"] = request_id
        _log_event(event_type="tool_result", payload=result_payload, client_id=request.client_id)
        tool_result_emitted = True

    return tool_result


def execute_tool_call(
    tool_name: str,
    args: dict,
    client_id: int,
    db: Session,
    pension_portfolio=None,
    force_max_exemption: bool = False,
    agent_reply: str | None = None,
    user_approved: bool = False,
    request_id: str | None = None,
    tool_call_id: str | None = None,
) -> object:
    req = get_current_tool_execution_request()
    policy_decision = get_current_tool_execution_policy_decision()
    intent_type = get_current_tool_execution_intent_type()
    streaming = get_current_tool_execution_streaming()

    if req is None:
        req_for_exec = ChatRequest(messages=[], client_id=client_id)
    else:
        if getattr(req, "client_id", None) is None:
            try:
                req_for_exec = req.model_copy(update={"client_id": client_id}, deep=True)
            except Exception:
                req_for_exec = ChatRequest(messages=list(getattr(req, "messages", []) or []), client_id=client_id)
        else:
            req_for_exec = req

    return execute_with_guard(
        request=req_for_exec,
        db=db,
        tool_name=tool_name,
        tool_call_id=tool_call_id,
        tool_args=args if isinstance(args, dict) else {},
        streaming=bool(streaming),
        policy_decision=policy_decision,
        intent_type=intent_type,
        pension_portfolio=pension_portfolio,
        force_max_exemption=force_max_exemption,
        agent_reply=agent_reply,
        user_approved=user_approved,
        request_id=request_id,
    )
