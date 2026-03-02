import json
import logging
import os
import re
from datetime import date
from typing import AsyncIterator, Iterator
from uuid import UUID, uuid4

from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.guards.advisor_behavior_guard import (
    STANDARD_BLOCK_MESSAGE,
    _ALLOWED_FORM_SECTION_RE,
    _COMMA_NUMBER_RE,
    _DECIMAL_RE,
    _DIGIT_RE,
    _FORBIDDEN_BYPASS_PHRASES,
    _FORBIDDEN_DECISION_PHRASES,
    _FORBIDDEN_HEBREW_PHRASES,
    _FORBIDDEN_PERCENT_WORDS,
    _FORBIDDEN_SYMBOLS,
    _LONG_NUMBER_RE,
    _MONEY_PERCENT_RE,
    _THOUSANDS_RE,
)
from app.guards.tool_intent_guard import (
    allow_tools_for_intent,
    get_tools_disabled_reason,
    is_conceptual_no_execute_request,
    sanitize_words_only_conceptual,
    sanitize_words_only_output,
)
from app.schemas.llm_chat import ChatMessage, ChatRequest, ChatResponse
from app.services.agent_eyes.event_collector import emit_event as _eyes_emit
from app.services.agent_execution.policy import PolicyDecision, decide
from app.services.agent_trace_logger import log_trace_event
from app.services.llm_chat.execution_only_fallback import build_execution_only_fallback
from app.services.llm_chat.execution_only_guard import (
    is_execution_only,
    validate_execution_only_output,
    get_execution_only_system_prompt,
)
from app.services.llm_chat.execution_only_rewriter import build_exec_only_rewrite_prompt
from app.services.llm_chat.explicit_tool_shortcuts import (
    CLIENT_SNAPSHOT_TOOL_NAME,
    extract_first_json,
    is_client_snapshot_shortcut_request,
    wants_json_only,
)
from app.services.llm_chat.intent_classifier import ChatIntent, detect_intent
from app.services.llm_chat.orchestration_core.core_types import (
    DecisionCode,
    OrchestrationDecision,
    OrchestrationDeps,
    OrchestrationInput,
    ToolResultEnvelope,
    TraceEventSpec,
)
from app.services.llm_chat.orchestration_core.orchestrate import orchestrate
from app.services.llm_chat.orchestration_core.constants import (
    MAX_ITERATIONS_USER_MESSAGE_HE,
)
from app.services.llm_chat.orchestration_core.max_iterations_guard import (
    maybe_apply_max_iterations_guard,
)
from app.services.llm_chat.orchestration_core.snapshot_enrichment import (
    enrich_state_snapshot,
)
from app.services.llm_chat.orchestration_core.state_apply import (
    apply_tool_result_to_state,
)
from app.services.llm_chat.orchestration_utils_parts.tool_names import (
    MONTHLY_PENSION_SUMMARY_TOOL_NAME,
    TERMINATION_CONCEPTUAL_NO_EXECUTE_REPLY_TOOL_NAME,
)
from app.services.llm_chat.orchestration_core.feature_flags import compute_feature_flags
from app.services.llm_chat.capability_router.router_facade import ensure_router_decision
from app.services.llm_chat.capability_router.runtime_context import (
    RouterDecision,
    get_router_decision,
)
from app.services.llm_chat.mcp.engine import MCPEngine, mcp_decision_to_payload
from app.services.llm_chat.mcp.decision import MCPDecision, MCPExecutionMode
from app.services.llm_chat.mcp.types import MCPOutcomeFinal
from app.services.intent_classifier import IntentType, classify_intent
from app.services.llm_pension_agent_service import pension_llm_service
from app.services.agent_execution.tool_execution_context import (
    get_tool_ok_seen,
    reset_tool_ok_seen,
    set_tool_execution_context,
)
from app.services.agent_execution.tool_executor import execute_with_guard

logger = logging.getLogger("app.llm_chat")


MAX_BUFFER_CHARS = 20_000


_LEGACY_REASON_CODES = {
    "CORE_DECISION_REQUESTED_LEGACY",
    "CORE_LOOP_DISABLED_BY_CONFIG",
    "UNHANDLED_CORE_ERROR",
    "UNKNOWN",
}


_ROUTER_DECISION_MISSING_REASON_CODES = {
    "ROUTER_DECISION_NOT_REQUESTED",
    "MISSING_CLIENT_ID",
    "RESOLVER_ERROR",
    "UNKNOWN",
}


_UI_ACTION_RE = re.compile(r"###UI_ACTION###.*?###END_UI_ACTION###", flags=re.DOTALL)
_COMPUTED_DATA_RE = re.compile(
    r"###COMPUTED_DATA###.*?###END_COMPUTED_DATA###", flags=re.DOTALL
)
_PENSION_PORTFOLIO_UPDATE_RE = re.compile(
    r"###PENSION_PORTFOLIO_UPDATE###.*?###END_PENSION_PORTFOLIO_UPDATE###(?:\r?\n)?",
    flags=re.DOTALL,
)
_TARGET_PENSION_PLAN_DATA_RE = re.compile(
    r"###TARGET_PENSION_PLAN_DATA###.*?###END_TARGET_PENSION_PLAN_DATA###(?:\r?\n)?",
    flags=re.DOTALL,
)


_TERMINATION_CONCEPTUAL_NO_EXECUTE_NON_STREAM_REPLY = (
    "כותרת: עזיבת עבודה – הסבר עקרוני (ללא ביצוע)\n\n"
    "לא נעשתה פעולה במערכת.\n\n"
    "מה בודקים ומחליטים בעזיבת עבודה (עקרונית):\n"
    "- תאריך סיום עבודה\n"
    "- סכום פיצויים והפרדה לפטור/חייב\n"
    "- בחירת טיפול בפיצויים: רצף קצבה / משיכה / שילוב\n"
)


_TERMINATION_CONCEPTUAL_NO_EXECUTE_STREAM_REPLY = (
    "כותרת: עזיבת עבודה – הסבר עקרוני (ללא ביצוע)\n\n"
    "לא נעשתה פעולה במערכת.\n\n"
    "מה קורה בעזיבת עבודה (ברמה עקרונית):\n"
    "- קובעים תאריך סיום עבודה\n"
    "- מפרידים פיצויים לפטור/חייב לפי נתוני המעסיק\n"
    "- בוחרים טיפול בפיצויים: רצף קצבה / משיכה / שילוב\n\n"
    "כדי לבצע בפועל בפנייה הבאה, כתוב במפורש 'בצע עזיבת עבודה' וציין את תאריך הסיום והבחירות."
)

_TRANSPARENCY_LOG_RE = re.compile(
    r"###TRANSPARENCY_LOG###.*?(?:\r?\n|$)",
    flags=re.DOTALL,
)
_RISK_REVIEW_RE = re.compile(
    r"###RISK_REVIEW###.*?(?:\r?\n|$)",
    flags=re.DOTALL,
)


def _strip_structured_blocks(text: str) -> str:
    if not isinstance(text, str) or not text:
        return ""
    out = _UI_ACTION_RE.sub("", text)
    out = _COMPUTED_DATA_RE.sub("", out)
    out = _PENSION_PORTFOLIO_UPDATE_RE.sub("", out)
    out = _TARGET_PENSION_PLAN_DATA_RE.sub("", out)
    out = _TRANSPARENCY_LOG_RE.sub("", out)
    out = _RISK_REVIEW_RE.sub("", out)
    return out


def _is_structured_payload_only(text: str | None) -> bool:
    if not isinstance(text, str) or not text.strip():
        return True

    stripped = text.strip()
    if (stripped.startswith("{") and stripped.endswith("}")) or (
        stripped.startswith("[") and stripped.endswith("]")
    ):
        return True

    visible = _strip_structured_blocks(stripped).strip()
    return visible == ""


def _has_tool_result_ok_for_current_trace() -> bool:
    try:
        if get_tool_ok_seen():
            return True
    except Exception:
        pass
    trace_id = None
    try:
        from app.utils.trace_context import get_current_trace_id

        trace_id = get_current_trace_id()
    except Exception:
        trace_id = None
    if not trace_id:
        return False

    try:
        from app.database import SessionLocal
        from app.models.agent_trace_event import AgentTraceEvent

        s = SessionLocal()
        try:
            rows = (
                s.query(AgentTraceEvent)
                .filter(AgentTraceEvent.trace_id == trace_id)
                .filter(AgentTraceEvent.event_type == "tool_result")
                .order_by(AgentTraceEvent.id.asc())
                .all()
            )
            for r in rows:
                payload_raw = getattr(r, "payload_json", None)
                if not isinstance(payload_raw, str) or not payload_raw.strip():
                    continue
                try:
                    payload = json.loads(payload_raw)
                except Exception:
                    continue
                if isinstance(payload, dict) and payload.get("status") == "ok":
                    return True
        finally:
            try:
                s.close()
            except Exception:
                pass
    except Exception:
        return False

    return False


def _build_stage10_blocked_reply() -> str:
    return STANDARD_BLOCK_MESSAGE


def _stage10_enforce_behavioral_limits(
    *, text: str, allow_numbers: bool
) -> tuple[bool, str]:
    candidate = text or ""

    if not allow_numbers:
        allowed_spans: list[tuple[int, int]] = []
        try:
            allowed_spans.extend(
                [
                    (m.start(), m.end())
                    for m in _ALLOWED_FORM_SECTION_RE.finditer(candidate)
                ]
            )
        except Exception:
            allowed_spans = []

        try:
            for m in re.finditer(r"(?m)^\s*(?:-\s*)?\d{1,3}(?=[\.)])", candidate):
                allowed_spans.append((m.start(), m.end()))
        except Exception:
            pass

        try:
            for m in re.finditer(r"(?i)(?:שלב|צעד)\s*\d{1,3}", candidate):
                allowed_spans.append((m.start(), m.end()))
        except Exception:
            pass

        def _is_span_allowed(start: int, end: int) -> bool:
            for a_start, a_end in allowed_spans:
                if start >= a_start and end <= a_end:
                    return True
            return False

        if _DIGIT_RE.search(candidate):
            if (
                _MONEY_PERCENT_RE.search(candidate)
                or _DECIMAL_RE.search(candidate)
                or _THOUSANDS_RE.search(candidate)
                or _COMMA_NUMBER_RE.search(candidate)
            ):
                return False, STANDARD_BLOCK_MESSAGE

            for m in re.finditer(r"\d+", candidate):
                if not _is_span_allowed(m.start(), m.end()):
                    return False, STANDARD_BLOCK_MESSAGE

            if _LONG_NUMBER_RE.search(candidate):
                for m in re.finditer(r"\d{4,}", candidate):
                    if not _is_span_allowed(m.start(), m.end()):
                        return False, STANDARD_BLOCK_MESSAGE

        if any(sym in candidate for sym in _FORBIDDEN_SYMBOLS):
            return False, STANDARD_BLOCK_MESSAGE

        if any(word in candidate for word in _FORBIDDEN_PERCENT_WORDS):
            return False, STANDARD_BLOCK_MESSAGE

    if any(phrase in candidate for phrase in _FORBIDDEN_HEBREW_PHRASES):
        return False, STANDARD_BLOCK_MESSAGE

    if any(phrase in candidate for phrase in _FORBIDDEN_DECISION_PHRASES):
        return False, STANDARD_BLOCK_MESSAGE

    if any(phrase in candidate for phrase in _FORBIDDEN_BYPASS_PHRASES):
        return False, STANDARD_BLOCK_MESSAGE

    return True, candidate


def _stage10_guard_reply_text(
    *, reply: str | None, endpoint: str, client_id: int | None, executor_only: bool
) -> str | None:
    if not isinstance(reply, str) or not reply.strip():
        return reply

    if bool(executor_only) is True:
        return reply

    had_tool_ok = _has_tool_result_ok_for_current_trace()

    if bool(had_tool_ok) is True:
        return reply

    candidate_text = reply.strip()

    if "###UI_ACTION###" in candidate_text and "###END_UI_ACTION###" in candidate_text:
        return reply

    # No tool_ok: prevent bypass via raw JSON payloads or computed_data-only blocks.
    try:
        if (
            _COMPUTED_DATA_RE.search(candidate_text)
            or _PENSION_PORTFOLIO_UPDATE_RE.search(candidate_text)
            or _TARGET_PENSION_PLAN_DATA_RE.search(candidate_text)
        ) and _strip_structured_blocks(candidate_text).strip() == "":
            return _build_stage10_blocked_reply()
    except Exception:
        pass

    try:
        if _is_structured_payload_only(candidate_text):
            return reply
    except Exception:
        pass

    visible_text = _strip_structured_blocks(candidate_text).strip()
    if not visible_text:
        # UI actions / markers are allowed to pass through as they are not user-visible numeric output.
        return reply

    allowed, _final_text = _stage10_enforce_behavioral_limits(
        text=visible_text,
        allow_numbers=False,
    )
    if allowed:
        return reply

    blocked_reply = _build_stage10_blocked_reply()
    try:
        examples: list[str] = []
        try:
            from app.services.llm_chat.numeric_provenance import (
                build_numeric_match_examples,
            )

            examples = build_numeric_match_examples(
                text=visible_text, window=30, max_examples=3
            )
        except Exception:
            examples = []

        log_trace_event(
            event_type="validation_error",
            payload={
                "error_code": "STAGE10_ASSISTANT_TEXT_GUARD_BLOCKED",
                "message": "Assistant visible text blocked by Stage 10 guard.",
                "endpoint": endpoint,
                "had_tool_execution_for_allowance": bool(had_tool_ok),
                "visible_text_preview": visible_text[:300],
                "numeric_match_examples": examples,
            },
            client_id=client_id,
            endpoint=endpoint,
        )
        _eyes_emit(
            "validation_error",
            {
                "error_code": "STAGE10_ASSISTANT_TEXT_GUARD_BLOCKED",
                "endpoint": endpoint,
            },
            client_id=client_id,
            endpoint=endpoint,
        )
    except Exception:
        pass
    return blocked_reply


def _find_last_user_message_text(request: ChatRequest) -> str:
    try:
        for m in reversed(request.messages or []):
            if getattr(m, "role", None) == "user":
                return (getattr(m, "content", "") or "").strip()
    except Exception:
        return ""
    return ""


def _build_monthly_pension_reply(payload: dict) -> str:
    _ = payload
    return "Monthly pension summary computed. See computed_data for details."


def _log_policy_decision(
    *, request: ChatRequest, intent: ChatIntent, decision: PolicyDecision, endpoint: str
) -> None:
    try:
        payload = {
            "intent": intent.value,
            "mode": getattr(decision.mode, "value", str(decision.mode)),
            "tools_allowed": bool(decision.tools_allowed),
            "write_allowed": bool(decision.write_allowed),
            "missing_params": list(getattr(decision, "missing_params", []) or []),
        }
        log_trace_event(
            event_type="policy_decision",
            payload=payload,
            client_id=request.client_id,
            endpoint=endpoint,
        )
        _eyes_emit(
            "policy_decision", payload, client_id=request.client_id, endpoint=endpoint
        )
    except Exception:
        pass


def _emit_final_response(
    *,
    reply: str | None,
    computed_data,
    streaming: bool,
    client_id: int | None,
    endpoint: str,
) -> None:
    try:
        text = reply if isinstance(reply, str) else ""
        stripped = text.lstrip()
        response_kind = (
            "structured_json"
            if (stripped.startswith("{") and stripped.rstrip().endswith("}"))
            else "text"
        )
        payload = {
            "response_kind": response_kind,
            "length_chars": len(text),
            "contained_tool_calls": ("###TOOL_CALL###" in text),
            "has_computed_data": computed_data is not None,
            "streaming": bool(streaming),
        }
        log_trace_event(
            event_type="final_response",
            payload=payload,
            client_id=client_id,
            endpoint=endpoint,
        )
        _eyes_emit("final_response", payload, client_id=client_id, endpoint=endpoint)
    except Exception:
        pass


def _apply_tools_policy_copy(
    request: ChatRequest,
    *,
    last_user_msg: str,
    intent: ChatIntent,
    policy_tools_allowed: bool,
) -> ChatRequest:
    effective = request.model_copy(deep=True)

    guard_tools_enabled = True
    guard_reason: str | None = None
    try:
        guard_tools_enabled = bool(allow_tools_for_intent(last_user_msg or "", intent))
        guard_reason = get_tools_disabled_reason(last_user_msg or "", intent)
    except Exception:
        guard_tools_enabled = True
        guard_reason = None

    effective_tools_enabled = bool(policy_tools_allowed) and bool(guard_tools_enabled)

    try:
        object.__setattr__(effective, "tools_enabled", bool(effective_tools_enabled))
        if not effective_tools_enabled:
            object.__setattr__(
                effective,
                "tools_disabled_reason",
                guard_reason or ("policy" if not policy_tools_allowed else None),
            )
    except Exception:
        pass
    return effective


def _apply_execution_only_prompt_copy(
    request: ChatRequest, *, last_user_msg: str, intent: ChatIntent
) -> ChatRequest:
    effective = request
    try:
        if is_execution_only(effective) and intent != ChatIntent.REPORT:
            msgs = list(effective.messages or [])
            if not (
                msgs
                and getattr(msgs[0], "role", None) == "system"
                and "מצב: EXECUTION_ONLY" in (getattr(msgs[0], "content", "") or "")
            ):
                msgs.insert(
                    0,
                    ChatMessage(
                        role="system", content=get_execution_only_system_prompt()
                    ),
                )
                object.__setattr__(effective, "messages", msgs)
    except Exception:
        pass
    return effective


def _enforce_execution_only_non_stream(
    *, request: ChatRequest, last_user_msg: str, response: ChatResponse
) -> ChatResponse:
    if not is_execution_only(request):
        return response

    if (
        isinstance(response.reply, str)
        and "###UI_ACTION###" in response.reply
        and "###END_UI_ACTION###" in response.reply
    ):
        return response

    try:
        validate_execution_only_output(response.reply)
        return response
    except Exception as e:
        rewritten: str | None = None
        try:
            rewrite_prompt = build_exec_only_rewrite_prompt(
                response.reply, last_user_msg
            )
            rewrite_messages = [
                ChatMessage(role=m["role"], content=m["content"])
                for m in rewrite_prompt
            ]
            rewritten = pension_llm_service.chat(rewrite_messages, request.client_id)
            validate_execution_only_output(rewritten)
            return ChatResponse(reply=rewritten, computed_data=response.computed_data)
        except Exception as e2:
            _ = (e, e2)
            fallback = build_execution_only_fallback(last_user_msg)
            return ChatResponse(reply=fallback, computed_data=None)


def _run_execution_only_non_stream(
    *, request: ChatRequest, last_user_msg: str
) -> ChatResponse:
    endpoint = "/api/v1/llm/pension-chat"

    try:
        _payload = {
            "executor_only": True,
            "last_user_message_preview": (last_user_msg or "")[:500],
        }
        log_trace_event(
            event_type="exec_only_entry",
            payload=_payload,
            client_id=request.client_id,
            endpoint=endpoint,
        )
        _eyes_emit(
            "exec_only_entry",
            _payload,
            client_id=request.client_id,
            endpoint=endpoint,
        )
    except Exception:
        pass

    effective_request = request.model_copy(deep=True)
    try:
        msgs = list(effective_request.messages or [])
        if not (
            msgs
            and getattr(msgs[0], "role", None) == "system"
            and "מצב: EXECUTION_ONLY" in (getattr(msgs[0], "content", "") or "")
        ):
            msgs.insert(
                0,
                ChatMessage(role="system", content=get_execution_only_system_prompt()),
            )
        object.__setattr__(effective_request, "messages", msgs)
    except Exception:
        pass

    raw = pension_llm_service.chat(
        list(effective_request.messages or []), effective_request.client_id
    )
    try:
        validate_execution_only_output(raw)
        return ChatResponse(reply=raw, computed_data=None)
    except Exception as e:
        rewritten: str | None = None
        try:
            rewrite_prompt = build_exec_only_rewrite_prompt(raw, last_user_msg)
            rewrite_messages = [
                ChatMessage(role=m["role"], content=m["content"])
                for m in rewrite_prompt
            ]
            rewritten = pension_llm_service.chat(
                rewrite_messages, effective_request.client_id
            )
            validate_execution_only_output(rewritten)
            return ChatResponse(reply=rewritten, computed_data=None)
        except Exception as e2:
            _ = (e, e2)
            fallback = build_execution_only_fallback(last_user_msg)
            return ChatResponse(reply=fallback, computed_data=None)


def execute_agent_request(request: ChatRequest, db: Session) -> ChatResponse:
    endpoint = "/api/v1/llm/pension-chat"

    try:
        reset_tool_ok_seen()
    except Exception:
        pass

    try:
        from app.utils.trace_context import (
            get_current_trace_id,
            generate_trace_id,
            set_current_trace_id,
        )

        _tid = get_current_trace_id() or generate_trace_id()
        set_current_trace_id(_tid)
        try:
            object.__setattr__(request, "trace_id", _tid)
        except Exception:
            pass
        try:
            if (
                db is not None
                and hasattr(db, "info")
                and isinstance(getattr(db, "info", None), dict)
            ):
                db.info["trace_id"] = _tid
        except Exception:
            pass
    except Exception:
        pass

    last_user_msg = _find_last_user_message_text(request)
    intent = detect_intent(last_user_msg)

    try:
        _tier_payload = {
            "intent_tier": str(
                getattr(intent, "name", None)
                or getattr(intent, "value", None)
                or str(intent)
            ),
            "source": "llm_chat.intent_classifier.detect_intent",
            "streaming": False,
        }
        log_trace_event(
            event_type="intent_tier_detected",
            payload=_tier_payload,
            client_id=request.client_id,
            endpoint=endpoint,
        )
        _eyes_emit(
            "intent_tier_detected",
            _tier_payload,
            client_id=request.client_id,
            endpoint=endpoint,
        )
    except Exception:
        pass

    _core_state_snapshot = {
        "executor_only": getattr(request, "executor_only", None),
    }
    _feature_flags = compute_feature_flags(
        request=request,
        user_text=last_user_msg,
        intent=intent,
        allow_greeting_shortcut=False,
        allow_exec_only_path=True,
    )
    _core_deps = OrchestrationDeps(
        llm_generate=lambda messages, client_id=None: pension_llm_service.chat(
            messages, client_id
        ),
        policy_gate=decide,
    )
    executor_only_flag = bool(getattr(request, "executor_only", None))

    try:
        _ui_payload = {
            "message_preview": (last_user_msg or "")[:500],
            "streaming": False,
            "executor_only": getattr(request, "executor_only", None),
        }
        log_trace_event(
            event_type="user_input",
            payload=_ui_payload,
            client_id=request.client_id,
            endpoint=endpoint,
        )
        _eyes_emit(
            "user_input", _ui_payload, client_id=request.client_id, endpoint=endpoint
        )
    except Exception:
        pass

    intent_type, rule_hit = classify_intent(user_message=last_user_msg, request=request)
    try:
        _it_payload = {
            "intent_type": getattr(intent_type, "value", str(intent_type)),
            "rule_hit": rule_hit,
            "message_preview": (last_user_msg or "")[:500],
            "streaming": False,
        }
        log_trace_event(
            event_type="intent_detected",
            payload=_it_payload,
            client_id=request.client_id,
            endpoint=endpoint,
        )
        _eyes_emit(
            "intent_detected",
            _it_payload,
            client_id=request.client_id,
            endpoint=endpoint,
        )
    except Exception:
        pass

    decision = decide(request=request, intent=intent, allow_write=False)

    _log_policy_decision(
        request=request, intent=intent, decision=decision, endpoint=endpoint
    )

    # STAGE_G_DISCOVERY: Additional decision-like trace events emitted per request.
    # - execution_mode contains a coarse tools_allowed / mode summary.
    # - capability_resolved / router_decision_missing contain capability_id and resolver health.
    try:
        _mode_payload = {
            "execution_mode": (
                "agent_mode" if bool(decision.tools_allowed) else "qa_mode"
            ),
            "tools_allowed": bool(decision.tools_allowed),
            "executor_only": getattr(request, "executor_only", None),
            "streaming": False,
        }
        log_trace_event(
            event_type="execution_mode",
            payload=_mode_payload,
            client_id=request.client_id,
            endpoint=endpoint,
        )
        _eyes_emit(
            "execution_mode",
            _mode_payload,
            client_id=request.client_id,
            endpoint=endpoint,
        )
    except Exception:
        pass

    effective_request = _apply_tools_policy_copy(
        request,
        last_user_msg=last_user_msg,
        intent=intent,
        policy_tools_allowed=bool(decision.tools_allowed),
    )
    effective_request = _apply_execution_only_prompt_copy(
        effective_request, last_user_msg=last_user_msg, intent=intent
    )
    try:
        _tid_req = getattr(request, "trace_id", None)
        if _tid_req:
            object.__setattr__(effective_request, "trace_id", _tid_req)
    except Exception:
        pass

    try:
        set_tool_execution_context(
            request=effective_request,
            policy_decision=decision,
            intent_type=intent_type,
            streaming=False,
        )
    except Exception:
        pass

    # Preamble is best effort telemetry only. Must not affect routing, fallback selection, state, or raise.
    _router_decision_guardrails_preamble_attempted = False

    def _router_decision_guardrails_preamble() -> None:
        nonlocal _router_decision_guardrails_preamble_attempted
        _router_decision_guardrails_preamble_attempted = True
        try:
            if getattr(request, "client_id", None) is None:
                _preamble_payload = {
                    "reason": "router_decision_guardrails_preamble",
                    "execution_path": "preamble",
                    "router_decision_missing_reason_code": "MISSING_CLIENT_ID",
                    "detail": "client_id_missing",
                }
                log_trace_event(
                    event_type="router_decision_missing",
                    payload=_preamble_payload,
                    client_id=getattr(request, "client_id", None),
                    endpoint=endpoint,
                )
                _eyes_emit(
                    "router_decision_missing",
                    _preamble_payload,
                    client_id=getattr(request, "client_id", None),
                    endpoint=endpoint,
                )
                return

            try:
                _decision = ensure_router_decision(
                    user_text=last_user_msg or "",
                    client_id=getattr(request, "client_id", None),
                    trace_id=getattr(request, "trace_id", None),
                )
            except Exception as e:
                _detail = "resolver_error"
                try:
                    _detail = f"{type(e).__name__}:{str(e)[:120]}".strip(":")
                except Exception:
                    _detail = "resolver_error"
                _preamble_payload = {
                    "reason": "router_decision_guardrails_preamble",
                    "execution_path": "preamble",
                    "router_decision_missing_reason_code": "RESOLVER_ERROR",
                    "detail": _detail,
                }
                log_trace_event(
                    event_type="router_decision_missing",
                    payload=_preamble_payload,
                    client_id=getattr(request, "client_id", None),
                    endpoint=endpoint,
                )
                _eyes_emit(
                    "router_decision_missing",
                    _preamble_payload,
                    client_id=getattr(request, "client_id", None),
                    endpoint=endpoint,
                )
                return

            _cap_id = ""
            try:
                _cap_id = str(getattr(_decision, "capability_id", "") or "")
            except Exception:
                _cap_id = ""

            if not _cap_id.strip():
                _preamble_payload = {
                    "reason": "router_decision_guardrails_preamble",
                    "execution_path": "preamble",
                    "router_decision_missing_reason_code": "UNKNOWN",
                    "detail": "empty_capability_id",
                }
                log_trace_event(
                    event_type="router_decision_missing",
                    payload=_preamble_payload,
                    client_id=getattr(request, "client_id", None),
                    endpoint=endpoint,
                )
                _eyes_emit(
                    "router_decision_missing",
                    _preamble_payload,
                    client_id=getattr(request, "client_id", None),
                    endpoint=endpoint,
                )
            else:
                try:
                    _cr_payload = {
                        "capability_id": _cap_id.strip(),
                        "decision_source": "ssot_runtime_router",
                    }
                    log_trace_event(
                        trace_id=getattr(request, "trace_id", None),
                        event_type="capability_resolved",
                        payload=_cr_payload,
                        client_id=getattr(request, "client_id", None),
                        endpoint=endpoint,
                    )
                    _eyes_emit(
                        "capability_resolved",
                        _cr_payload,
                        client_id=getattr(request, "client_id", None),
                        endpoint=endpoint,
                    )
                except Exception:
                    pass
        except Exception:
            return

    _router_decision_guardrails_preamble()

    _MCP_NON_QA_FALLBACK_REASON = "BEHAVIOR_NOT_ACTIVATED"

    mcp_decision: MCPDecision
    # STAGE_G_DISCOVERY: MCPDecision is evaluated once here via MCPEngine().evaluate(...)
    # and later used to gate tool execution.
    try:
        _tier = str(
            getattr(intent, "name", None)
            or getattr(intent, "value", None)
            or str(intent)
        )
        _it = None
        try:
            _it = getattr(intent_type, "value", None) or str(intent_type)
        except Exception:
            _it = None

        _rd = None
        try:
            _rd = get_router_decision(trace_id=getattr(request, "trace_id", None))
        except Exception:
            _rd = None

        _is_snapshot_shortcut = False
        try:
            _is_snapshot_shortcut = bool(
                is_client_snapshot_shortcut_request(last_user_msg or "")
            )
        except Exception:
            _is_snapshot_shortcut = False

        if _is_snapshot_shortcut:
            try:
                tc = getattr(_rd, "tool_chain", None) if _rd is not None else None
                if not (isinstance(tc, list) and len(tc) > 0):
                    if _rd is None:
                        _rd = RouterDecision(
                            capability_id="default_qa_v1",
                            mode="QA",
                            tool_chain=[CLIENT_SNAPSHOT_TOOL_NAME],
                            output_schema_id="snapshot_shortcut_v1",
                            capability_map_version="",
                            router_normalization_version="",
                            normalized_text_hash="",
                        )
                    else:
                        _rd = RouterDecision(
                            capability_id=str(getattr(_rd, "capability_id", "") or ""),
                            mode=str(getattr(_rd, "mode", "") or "QA"),
                            tool_chain=[CLIENT_SNAPSHOT_TOOL_NAME],
                            output_schema_id=str(
                                getattr(_rd, "output_schema_id", "") or ""
                            ),
                            capability_map_version=str(
                                getattr(_rd, "capability_map_version", "") or ""
                            ),
                            router_normalization_version=str(
                                getattr(_rd, "router_normalization_version", "") or ""
                            ),
                            normalized_text_hash=str(
                                getattr(_rd, "normalized_text_hash", "") or ""
                            ),
                        )
            except Exception:
                pass

        _tools_enabled = getattr(effective_request, "tools_enabled", None)
        _tools_disabled_reason = getattr(
            effective_request, "tools_disabled_reason", None
        )
        try:
            if _rd is not None:
                _cap_id = str(getattr(_rd, "capability_id", "") or "")
                if not _cap_id.strip():
                    _tools_enabled = False
                    _tools_disabled_reason = "SSOT_INVALID_NO_DEFAULT_QA"
        except Exception:
            pass

        _guard_result = {
            "tools_enabled": _tools_enabled,
            "tools_disabled_reason": _tools_disabled_reason,
        }

        mcp_decision = MCPEngine().evaluate(
            intent_tier=_tier,
            intent_type=str(_it) if _it is not None else None,
            router_decision=_rd,
            guard_result=_guard_result,
            had_new_core_entered=False,
            legacy_requested=False,
        )
    except Exception:
        mcp_decision = MCPDecision(
            execution_mode=MCPExecutionMode.TOOL_BLOCKED,
            reason_code="mcp_error",
            capability_id=None,
            intent_tier="UNKNOWN",
            intent_type=None,
        )

    # STAGE_G_DISCOVERY: MCPDecision trace emission callsite (event_type='mcp_decision').
    # NOTE: log_trace_event(...) already calls agent_eyes.emit_event internally.
    # The explicit _eyes_emit('mcp_decision', ...) below is a second emit for the same request.
    # Stage G will lock a single canonical MCPDecision emit; legacy duplicates are tagged.
    try:
        _payload = mcp_decision_to_payload(mcp_decision)
        log_trace_event(
            trace_id=getattr(request, "trace_id", None),
            event_type="mcp_decision",
            payload=_payload,
            client_id=getattr(request, "client_id", None),
            endpoint=endpoint,
        )
    except Exception:
        pass

    _new_core_entered_emitted = False

    _MAX_CORE_TOOL_ITERATIONS = 4
    _core_last_tool_result: ToolResultEnvelope | None = None
    _core_final_computed_data = None
    _core_final_computed_data_marker: str | None = None
    _core_final_reply_override: str | None = None
    _core_decision = None
    _core_iterations_completed = 0

    for _iter_idx in range(_MAX_CORE_TOOL_ITERATIONS):
        _core_input = OrchestrationInput(
            user_text=last_user_msg or "",
            client_id=getattr(request, "client_id", None),
            session_id=getattr(request, "session_id", None),
            conversation_id=getattr(request, "conversation_id", None),
            trace_id=getattr(request, "trace_id", None),
            feature_flags=_feature_flags,
            request_meta=None,
            state_snapshot=_core_state_snapshot,
            last_tool_result=_core_last_tool_result,
        )
        _core_decision, _core_trace_specs = orchestrate(_core_input, _core_deps)
        _core_iterations_completed = _iter_idx + 1

        _core_decision, _core_trace_specs, _max_iter_triggered = (
            maybe_apply_max_iterations_guard(
                iter_idx=_iter_idx,
                max_iterations=_MAX_CORE_TOOL_ITERATIONS,
                trace_id=getattr(request, "trace_id", None),
                final_text=MAX_ITERATIONS_USER_MESSAGE_HE,
                decision=_core_decision,
                trace_specs=_core_trace_specs,
            )
        )

        _is_legacy_fallback_decision = False
        try:
            _dm = getattr(_core_decision, "debug_meta", None)
            if isinstance(_dm, dict):
                _is_legacy_fallback_decision = bool(_dm.get("legacy_fallback", False))
        except Exception:
            _is_legacy_fallback_decision = False

        if (not _is_legacy_fallback_decision) and (not _new_core_entered_emitted):
            try:
                _nce_payload = {
                    "execution_path": "new_core",
                    "streaming": False,
                    "source": "agent_execution.execute_agent_request",
                }
                log_trace_event(
                    event_type="new_core_entered",
                    payload=_nce_payload,
                    client_id=request.client_id,
                    endpoint=endpoint,
                )
                _eyes_emit(
                    "new_core_entered",
                    _nce_payload,
                    client_id=request.client_id,
                    endpoint=endpoint,
                )
                _new_core_entered_emitted = True
            except Exception:
                pass

        if (
            _iter_idx == 0
            and _new_core_entered_emitted
            and (not _is_legacy_fallback_decision)
        ):
            try:
                _rd = get_router_decision(trace_id=getattr(request, "trace_id", None))
                _cap_id = str(getattr(_rd, "capability_id", "") or "") if _rd else ""
                if not _cap_id.strip():
                    _missing_reason_code = "UNKNOWN"
                    try:
                        if getattr(request, "client_id", None) is None:
                            _missing_reason_code = "MISSING_CLIENT_ID"
                        elif _rd is None or getattr(request, "trace_id", None) is None:
                            if _router_decision_preamble_attempted:
                                _missing_reason_code = "RESOLVER_ERROR"
                            else:
                                _missing_reason_code = "ROUTER_DECISION_NOT_REQUESTED"
                        else:
                            _missing_reason_code = "RESOLVER_ERROR"
                    except Exception:
                        _missing_reason_code = "UNKNOWN"

                    _missing_payload = {
                        "reason": "missing_router_decision_in_new_core",
                        "execution_path": "new_core",
                        "router_decision_missing_reason_code": _missing_reason_code,
                    }
                    log_trace_event(
                        event_type="router_decision_missing",
                        payload=_missing_payload,
                        client_id=request.client_id,
                        endpoint=endpoint,
                    )
                    _eyes_emit(
                        "router_decision_missing",
                        _missing_payload,
                        client_id=request.client_id,
                        endpoint=endpoint,
                    )
            except Exception:
                pass

        if not _is_legacy_fallback_decision:
            try:
                _dc = getattr(_core_decision, "decision_code", None)
                _dc_s = str(getattr(_dc, "value", None) or _dc or "")
                _lp_payload = {
                    "decision_code": _dc_s,
                    "tool_call_requested": _dc == DecisionCode.TOOL_CALL,
                    "tools_requested_count": 1 if _dc == DecisionCode.TOOL_CALL else 0,
                }
                log_trace_event(
                    event_type="loop_policy_evaluated",
                    payload=_lp_payload,
                    client_id=request.client_id,
                    endpoint=endpoint,
                )
                _eyes_emit(
                    "loop_policy_evaluated",
                    _lp_payload,
                    client_id=request.client_id,
                    endpoint=endpoint,
                )
            except Exception:
                pass
        for spec in _core_trace_specs:
            try:
                log_trace_event(
                    trace_id=spec.trace_id,
                    event_type=spec.event_type,
                    payload=spec.payload,
                    client_id=request.client_id,
                    endpoint=endpoint,
                )
                _eyes_emit(
                    spec.event_type,
                    spec.payload,
                    client_id=request.client_id,
                    endpoint=endpoint,
                )
            except Exception:
                pass

        if _max_iter_triggered:
            break

        if getattr(_core_decision, "decision_code", None) != DecisionCode.TOOL_CALL:
            break

        outcome_final = mcp_decision.outcome_final or MCPOutcomeFinal.TOOL_BLOCKED
        if outcome_final != MCPOutcomeFinal.TOOL_ALLOWED:
            if outcome_final == MCPOutcomeFinal.NO_TOOLS:
                raw = pension_llm_service.chat(
                    list(effective_request.messages or []), effective_request.client_id
                )
                res = ChatResponse(reply=raw, computed_data=None)
            elif outcome_final == MCPOutcomeFinal.PENDING_APPROVAL:
                res = ChatResponse(
                    reply=(
                        "נדרש אישור כדי לבצע. שלח בקשה חדשה אחרי אישור. "
                        f"reason_code={mcp_decision.reason_code}"
                    ),
                    computed_data=None,
                )
            else:
                res = ChatResponse(
                    reply=(
                        "הבקשה נחסמה לפי מדיניות. "
                        f"reason_code={mcp_decision.reason_code}"
                    ),
                    computed_data=None,
                )

            res.reply = _stage10_guard_reply_text(
                reply=getattr(res, "reply", None),
                endpoint=endpoint,
                client_id=effective_request.client_id,
                executor_only=executor_only_flag,
            )
            _emit_final_response(
                reply=getattr(res, "reply", None),
                computed_data=getattr(res, "computed_data", None),
                streaming=False,
                client_id=effective_request.client_id,
                endpoint=endpoint,
            )
            return res

        tool_name = getattr(_core_decision, "tool_name", None)
        _core_args = getattr(_core_decision, "tool_args", None)
        tool_args = _core_args if isinstance(_core_args, dict) else {}

        tool_call_id = None
        try:
            tool_call_id = uuid4().hex
        except Exception:
            tool_call_id = None

        tool_result_payload = None
        computed_data = None
        if tool_name == "EXECUTION_ONLY":
            _res = _run_execution_only_non_stream(
                request=request, last_user_msg=last_user_msg
            )
            tool_result_payload = getattr(_res, "reply", None)
        elif (
            tool_name == MONTHLY_PENSION_SUMMARY_TOOL_NAME
            and effective_request.client_id is not None
        ):
            raw_tool_result = execute_with_guard(
                request=effective_request,
                db=db,
                tool_name=MONTHLY_PENSION_SUMMARY_TOOL_NAME,
                tool_call_id=tool_call_id,
                tool_args=tool_args,
                streaming=False,
                policy_decision=decision,
                intent_type=intent_type,
                pension_portfolio=getattr(effective_request, "pension_portfolio", None),
                force_max_exemption=False,
                agent_reply=None,
                user_approved=True,
                request_id=None,
            )
            parsed = None
            try:
                parsed = (
                    json.loads(raw_tool_result)
                    if isinstance(raw_tool_result, str)
                    else None
                )
            except Exception:
                parsed = None

            if isinstance(parsed, dict):
                reply = parsed.get("reply")
                computed_data = parsed.get("computed_data")
                marker = parsed.get("computed_data_marker")
                if isinstance(reply, str) and reply.strip():
                    _core_final_reply_override = reply
                if isinstance(computed_data, dict):
                    _core_final_computed_data = computed_data
                if isinstance(marker, str) and marker:
                    _core_final_computed_data_marker = marker
                tool_result_payload = parsed
            else:
                tool_result_payload = raw_tool_result
        elif tool_name == CLIENT_SNAPSHOT_TOOL_NAME:
            raw_tool_result = execute_with_guard(
                request=effective_request,
                db=db,
                tool_name=CLIENT_SNAPSHOT_TOOL_NAME,
                tool_call_id=tool_call_id,
                tool_args=tool_args,
                streaming=False,
                policy_decision=decision,
                intent_type=intent_type,
                pension_portfolio=getattr(effective_request, "pension_portfolio", None),
                force_max_exemption=False,
                agent_reply=None,
                user_approved=True,
                request_id=None,
            )

            parsed = raw_tool_result if isinstance(raw_tool_result, dict) else None
            if isinstance(parsed, dict):
                # partial_result_v1 or tool result dict
                computed_data = parsed
                _core_final_computed_data = parsed
                tool_result_payload = parsed
                # Prefer tool-provided reply if exists, else emit a minimal message.
                reply = (
                    parsed.get("reply")
                    if isinstance(parsed.get("reply"), str)
                    else None
                )
                if isinstance(reply, str) and reply.strip():
                    _core_final_reply_override = reply
                else:
                    status = parsed.get("status")
                    if status == "missing_data":
                        _core_final_reply_override = (
                            "חסרים נתונים להפעלת הכלי. אנא ספק client_id."
                        )
                    elif status == "policy_blocked":
                        _core_final_reply_override = "הבקשה נחסמה לפי מדיניות. נסה לנסח מחדש או לבקש פעולה מותרת."
                    elif status == "schema_error":
                        _core_final_reply_override = (
                            "תקלה במבנה נתוני הכלי. נסה שוב או פנה לתמיכה."
                        )
                    elif status == "budget_exceeded":
                        _core_final_reply_override = (
                            "הבקשה חרגה מתקציב. נסה שוב מאוחר יותר."
                        )
            else:
                # Backwards compatibility: string JSON tool output
                tool_result_payload = raw_tool_result
                try:
                    parsed_str = (
                        json.loads(raw_tool_result)
                        if isinstance(raw_tool_result, str)
                        else None
                    )
                except Exception:
                    parsed_str = None
                if isinstance(parsed_str, dict):
                    computed_data = parsed_str
                    _core_final_computed_data = parsed_str
                    tool_result_payload = parsed_str
        elif tool_name == TERMINATION_CONCEPTUAL_NO_EXECUTE_REPLY_TOOL_NAME:
            reply = _TERMINATION_CONCEPTUAL_NO_EXECUTE_NON_STREAM_REPLY
            tool_result_payload = reply
        else:
            break

        _core_last_tool_result = ToolResultEnvelope(
            tool_name=str(tool_name or ""),
            tool_args=tool_args,
            tool_result=tool_result_payload,
            status="ok",
            error_message=None,
            trace_id=getattr(request, "trace_id", None),
            tool_call_id=tool_call_id,
        )

        _core_state_snapshot = enrich_state_snapshot(
            _core_state_snapshot,
            user_text=last_user_msg or "",
            last_tool_result=_core_last_tool_result,
        )
        _core_state_snapshot = apply_tool_result_to_state(
            _core_state_snapshot, _core_last_tool_result
        )

    if (
        _core_decision is not None
        and getattr(_core_decision, "decision_code", None) == DecisionCode.RESPOND_ONLY
    ):
        _final_text = getattr(_core_decision, "final_text", None)
        _final_text_s = _final_text if isinstance(_final_text, str) else ""
        _final_text_s = _final_text_s if _final_text_s.strip() else ""

        reply = ""
        if (
            isinstance(_core_final_reply_override, str)
            and _core_final_reply_override.strip()
        ):
            reply = _core_final_reply_override
        else:
            reply = _final_text_s

        if (reply or "").strip() or _core_final_computed_data is not None:
            try:
                if wants_json_only(last_user_msg) and isinstance(
                    _core_final_computed_data, dict
                ):
                    reply = json.dumps(_core_final_computed_data, ensure_ascii=False)
            except Exception:
                pass

            res = ChatResponse(reply=reply, computed_data=_core_final_computed_data)
            res.reply = _stage10_guard_reply_text(
                reply=getattr(res, "reply", None),
                endpoint=endpoint,
                client_id=effective_request.client_id,
                executor_only=executor_only_flag,
            )
            _emit_final_response(
                reply=res.reply,
                computed_data=res.computed_data,
                streaming=False,
                client_id=effective_request.client_id,
                endpoint=endpoint,
            )

            try:
                _ep_payload = {"execution_path": "new_core"}
                log_trace_event(
                    event_type="execution_path_selected",
                    payload=_ep_payload,
                    client_id=effective_request.client_id,
                    endpoint=endpoint,
                )
                _eyes_emit(
                    "execution_path_selected",
                    _ep_payload,
                    client_id=effective_request.client_id,
                    endpoint=endpoint,
                )
            except Exception:
                pass
            return res

        # If we got RESPOND_ONLY but no usable reply/computed_data, allow legacy fallback.

    try:
        _dc = getattr(_core_decision, "decision_code", None)
        _dc_s = str(getattr(_dc, "value", None) or _dc or "")
        _router_decision_guardrails_preamble()
        _legacy_reason_code = "UNKNOWN"
        try:
            _dm = getattr(_core_decision, "debug_meta", None)
            if isinstance(_dm, dict) and bool(_dm.get("legacy_fallback", False)):
                _legacy_reason_code = "CORE_DECISION_REQUESTED_LEGACY"
            elif _MAX_CORE_TOOL_ITERATIONS <= 0:
                _legacy_reason_code = "CORE_LOOP_DISABLED_BY_CONFIG"
        except Exception:
            _legacy_reason_code = "UNKNOWN"
        if _legacy_reason_code not in _LEGACY_REASON_CODES:
            _legacy_reason_code = "UNKNOWN"

        _legacy_payload = {
            "execution_path": "legacy_fallback",
            "legacy_entrypoint": "run_pension_chat",
            "reason": "core_decision_code:" + (_dc_s or "none"),
            "legacy_reason_code": _legacy_reason_code,
            "had_new_core_entered": bool(_new_core_entered_emitted),
            "core_iterations_completed": _core_iterations_completed,
        }
        log_trace_event(
            event_type="legacy_fallback_entered",
            payload=_legacy_payload,
            client_id=effective_request.client_id,
            endpoint=endpoint,
        )
        _eyes_emit(
            "legacy_fallback_entered",
            _legacy_payload,
            client_id=effective_request.client_id,
            endpoint=endpoint,
        )
    except Exception:
        pass

    from app.services.llm_chat.chat_orchestration import (
        run_pension_chat as run_pension_chat_service,
    )

    outcome_final = mcp_decision.outcome_final or MCPOutcomeFinal.TOOL_BLOCKED
    if outcome_final == MCPOutcomeFinal.PENDING_APPROVAL:
        reply = (
            "נדרש אישור כדי לבצע. שלח בקשה חדשה אחרי אישור. "
            f"reason_code={mcp_decision.reason_code}"
        )
        res = ChatResponse(reply=reply, computed_data=None)
        res.reply = _stage10_guard_reply_text(
            reply=getattr(res, "reply", None),
            endpoint=endpoint,
            client_id=effective_request.client_id,
            executor_only=executor_only_flag,
        )
        _emit_final_response(
            reply=getattr(res, "reply", None),
            computed_data=getattr(res, "computed_data", None),
            streaming=False,
            client_id=effective_request.client_id,
            endpoint=endpoint,
        )
        return res

    if outcome_final == MCPOutcomeFinal.TOOL_BLOCKED:
        reply = f"הבקשה נחסמה לפי מדיניות. reason_code={mcp_decision.reason_code}"
        res = ChatResponse(reply=reply, computed_data=None)
        res.reply = _stage10_guard_reply_text(
            reply=getattr(res, "reply", None),
            endpoint=endpoint,
            client_id=effective_request.client_id,
            executor_only=executor_only_flag,
        )
        _emit_final_response(
            reply=getattr(res, "reply", None),
            computed_data=getattr(res, "computed_data", None),
            streaming=False,
            client_id=effective_request.client_id,
            endpoint=endpoint,
        )
        return res

    res = run_pension_chat_service(effective_request, db)

    if (
        not isinstance(getattr(res, "reply", None), str)
        or not (res.reply or "").strip()
    ):
        if getattr(res, "computed_data", None) is not None and isinstance(
            res.computed_data, dict
        ):
            try:
                res.reply = _build_monthly_pension_reply(res.computed_data)
            except Exception:
                res.reply = "🔧 לא התקבלה תשובה מהמערכת. נסה לנסח מחדש."
        else:
            res.reply = "🔧 לא התקבלה תשובה מהמערכת. נסה לנסח מחדש."

    res = _enforce_execution_only_non_stream(
        request=effective_request, last_user_msg=last_user_msg, response=res
    )

    if (
        isinstance(res.reply, str)
        and "###UI_ACTION###" not in res.reply
        and "###END_UI_ACTION###" not in res.reply
    ):
        try:
            if bool(getattr(effective_request, "tools_enabled", True)) is False:
                res.reply = sanitize_words_only_output(res.reply)
        except Exception:
            pass

    res.reply = _stage10_guard_reply_text(
        reply=getattr(res, "reply", None),
        endpoint=endpoint,
        client_id=effective_request.client_id,
        executor_only=executor_only_flag,
    )

    try:
        if wants_json_only(last_user_msg) and isinstance(res.reply, str):
            extracted = extract_first_json(res.reply)
            if extracted is not None:
                res.reply = extracted
    except Exception:
        pass

    try:
        _ao_payload = {
            "reply_length": len(res.reply or ""),
            "reply_preview": (res.reply or "")[:2000],
            "has_computed_data": res.computed_data is not None,
            "streaming": False,
        }
        log_trace_event(
            event_type="assistant_output",
            payload=_ao_payload,
            client_id=effective_request.client_id,
            endpoint=endpoint,
        )
        _eyes_emit(
            "assistant_output",
            _ao_payload,
            client_id=effective_request.client_id,
            endpoint=endpoint,
        )
    except Exception:
        pass

    _emit_final_response(
        reply=getattr(res, "reply", None),
        computed_data=getattr(res, "computed_data", None),
        streaming=False,
        client_id=effective_request.client_id,
        endpoint=endpoint,
    )

    return res


def execute_agent_request_stream(
    request: ChatRequest, db: Session
) -> StreamingResponse:
    # STREAM_LOOP_FN: execute_agent_request_stream
    endpoint = "/api/v1/llm/pension-chat-stream"

    try:
        reset_tool_ok_seen()
    except Exception:
        pass

    _trace_id_for_stream = None
    try:
        from app.utils.trace_context import (
            get_current_trace_id,
            generate_trace_id,
            set_current_trace_id,
        )

        _trace_id_for_stream = get_current_trace_id() or generate_trace_id()
        set_current_trace_id(_trace_id_for_stream)
        try:
            object.__setattr__(request, "trace_id", _trace_id_for_stream)
        except Exception:
            pass
        try:
            if (
                db is not None
                and hasattr(db, "info")
                and isinstance(getattr(db, "info", None), dict)
            ):
                db.info["trace_id"] = _trace_id_for_stream
        except Exception:
            pass
    except Exception:
        _trace_id_for_stream = None

    last_user_msg = _find_last_user_message_text(request)
    intent = detect_intent(last_user_msg)

    try:
        _tier_payload = {
            "intent_tier": str(
                getattr(intent, "name", None)
                or getattr(intent, "value", None)
                or str(intent)
            ),
            "source": "llm_chat.intent_classifier.detect_intent",
            "streaming": True,
        }
        log_trace_event(
            event_type="intent_tier_detected",
            payload=_tier_payload,
            client_id=request.client_id,
            endpoint=endpoint,
        )
        _eyes_emit(
            "intent_tier_detected",
            _tier_payload,
            client_id=request.client_id,
            endpoint=endpoint,
        )
    except Exception:
        pass

    _core_state_snapshot = {
        "executor_only": getattr(request, "executor_only", None),
    }
    _feature_flags = compute_feature_flags(
        request=request,
        user_text=last_user_msg,
        intent=intent,
        allow_greeting_shortcut=True,
        allow_exec_only_path=False,
    )
    _core_deps = OrchestrationDeps(
        llm_generate=lambda messages, client_id=None: pension_llm_service.chat(
            messages, client_id
        ),
        policy_gate=decide,
    )

    try:
        _ui_payload = {
            "message_preview": (last_user_msg or "")[:500],
            "streaming": True,
            "executor_only": getattr(request, "executor_only", None),
        }
        log_trace_event(
            event_type="user_input",
            payload=_ui_payload,
            client_id=request.client_id,
            endpoint=endpoint,
        )
        _eyes_emit(
            "user_input", _ui_payload, client_id=request.client_id, endpoint=endpoint
        )
    except Exception:
        pass

    intent_type, rule_hit = classify_intent(user_message=last_user_msg, request=request)
    try:
        _it_payload = {
            "intent_type": getattr(intent_type, "value", str(intent_type)),
            "rule_hit": rule_hit,
            "message_preview": (last_user_msg or "")[:500],
            "streaming": True,
        }
        log_trace_event(
            event_type="intent_detected",
            payload=_it_payload,
            client_id=request.client_id,
            endpoint=endpoint,
        )
        _eyes_emit(
            "intent_detected",
            _it_payload,
            client_id=request.client_id,
            endpoint=endpoint,
        )
    except Exception:
        pass

    # reuse intent computed earlier
    decision = decide(request=request, intent=intent, allow_write=False)

    _log_policy_decision(
        request=request, intent=intent, decision=decision, endpoint=endpoint
    )

    # STAGE_G_DISCOVERY: Additional decision-like trace events emitted per request.
    # - execution_mode contains a coarse tools_allowed / mode summary.
    try:
        _mode_payload = {
            "execution_mode": (
                "agent_mode" if bool(decision.tools_allowed) else "qa_mode"
            ),
            "tools_allowed": bool(decision.tools_allowed),
            "executor_only": getattr(request, "executor_only", None),
            "streaming": True,
        }
        log_trace_event(
            event_type="execution_mode",
            payload=_mode_payload,
            client_id=request.client_id,
            endpoint=endpoint,
        )
        _eyes_emit(
            "execution_mode",
            _mode_payload,
            client_id=request.client_id,
            endpoint=endpoint,
        )
    except Exception:
        pass

    effective_request = _apply_tools_policy_copy(
        request,
        last_user_msg=last_user_msg,
        intent=intent,
        policy_tools_allowed=bool(decision.tools_allowed),
    )

    try:
        _tid_req = getattr(request, "trace_id", None)
        if _tid_req:
            object.__setattr__(effective_request, "trace_id", _tid_req)
    except Exception:
        pass

    try:
        set_tool_execution_context(
            request=effective_request,
            policy_decision=decision,
            intent_type=intent_type,
            streaming=True,
        )
    except Exception:
        pass

    # Preamble is best effort telemetry only. Must not affect routing, fallback selection, state, or raise.
    _router_decision_preamble_attempted = False

    def _router_decision_guardrails_preamble() -> None:
        nonlocal _router_decision_preamble_attempted
        _router_decision_preamble_attempted = True
        try:
            if getattr(request, "client_id", None) is None:
                _preamble_payload = {
                    "reason": "router_decision_guardrails_preamble",
                    "execution_path": "preamble",
                    "router_decision_missing_reason_code": "MISSING_CLIENT_ID",
                    "detail": "client_id_missing",
                }
                log_trace_event(
                    event_type="router_decision_missing",
                    payload=_preamble_payload,
                    client_id=getattr(request, "client_id", None),
                    endpoint=endpoint,
                )
                _eyes_emit(
                    "router_decision_missing",
                    _preamble_payload,
                    client_id=getattr(request, "client_id", None),
                    endpoint=endpoint,
                )
                return

            try:
                _decision = ensure_router_decision(
                    user_text=last_user_msg or "",
                    client_id=getattr(request, "client_id", None),
                    trace_id=getattr(request, "trace_id", None),
                )
            except Exception as e:
                _detail = "resolver_error"
                try:
                    _detail = f"{type(e).__name__}:{str(e)[:120]}".strip(":")
                except Exception:
                    _detail = "resolver_error"
                _preamble_payload = {
                    "reason": "router_decision_guardrails_preamble",
                    "execution_path": "preamble",
                    "router_decision_missing_reason_code": "RESOLVER_ERROR",
                    "detail": _detail,
                }
                log_trace_event(
                    event_type="router_decision_missing",
                    payload=_preamble_payload,
                    client_id=getattr(request, "client_id", None),
                    endpoint=endpoint,
                )
                _eyes_emit(
                    "router_decision_missing",
                    _preamble_payload,
                    client_id=getattr(request, "client_id", None),
                    endpoint=endpoint,
                )
                return

            _cap_id = ""
            try:
                _cap_id = str(getattr(_decision, "capability_id", "") or "")
            except Exception:
                _cap_id = ""

            if not _cap_id.strip():
                _preamble_payload = {
                    "reason": "router_decision_guardrails_preamble",
                    "execution_path": "preamble",
                    "router_decision_missing_reason_code": "UNKNOWN",
                    "detail": "empty_capability_id",
                }
                log_trace_event(
                    event_type="router_decision_missing",
                    payload=_preamble_payload,
                    client_id=getattr(request, "client_id", None),
                    endpoint=endpoint,
                )
                _eyes_emit(
                    "router_decision_missing",
                    _preamble_payload,
                    client_id=getattr(request, "client_id", None),
                    endpoint=endpoint,
                )
            else:
                try:
                    _cr_payload = {
                        "capability_id": _cap_id.strip(),
                        "decision_source": "ssot_runtime_router",
                    }
                    log_trace_event(
                        trace_id=getattr(request, "trace_id", None),
                        event_type="capability_resolved",
                        payload=_cr_payload,
                        client_id=getattr(request, "client_id", None),
                        endpoint=endpoint,
                    )
                    _eyes_emit(
                        "capability_resolved",
                        _cr_payload,
                        client_id=getattr(request, "client_id", None),
                        endpoint=endpoint,
                    )
                except Exception:
                    pass
        except Exception:
            return

    _router_decision_guardrails_preamble()

    _MCP_NON_QA_FALLBACK_REASON = "BEHAVIOR_NOT_ACTIVATED"

    mcp_decision: MCPDecision
    # STAGE_G_DISCOVERY: MCPDecision is evaluated once here via MCPEngine().evaluate(...)
    # and later used to gate tool execution.
    try:
        _tier = str(
            getattr(intent, "name", None)
            or getattr(intent, "value", None)
            or str(intent)
        )
        _it = None
        try:
            _it = getattr(intent_type, "value", None) or str(intent_type)
        except Exception:
            _it = None

        _rd = None
        try:
            _rd = get_router_decision(trace_id=getattr(request, "trace_id", None))
        except Exception:
            _rd = None

        _is_snapshot_shortcut = False
        try:
            _is_snapshot_shortcut = bool(
                is_client_snapshot_shortcut_request(last_user_msg or "")
            )
        except Exception:
            _is_snapshot_shortcut = False

        if _is_snapshot_shortcut:
            try:
                tc = getattr(_rd, "tool_chain", None) if _rd is not None else None
                if not (isinstance(tc, list) and len(tc) > 0):
                    if _rd is None:
                        _rd = RouterDecision(
                            capability_id="default_qa_v1",
                            mode="QA",
                            tool_chain=[CLIENT_SNAPSHOT_TOOL_NAME],
                            output_schema_id="snapshot_shortcut_v1",
                            capability_map_version="",
                            router_normalization_version="",
                            normalized_text_hash="",
                        )
                    else:
                        _rd = RouterDecision(
                            capability_id=str(getattr(_rd, "capability_id", "") or ""),
                            mode=str(getattr(_rd, "mode", "") or "QA"),
                            tool_chain=[CLIENT_SNAPSHOT_TOOL_NAME],
                            output_schema_id=str(
                                getattr(_rd, "output_schema_id", "") or ""
                            ),
                            capability_map_version=str(
                                getattr(_rd, "capability_map_version", "") or ""
                            ),
                            router_normalization_version=str(
                                getattr(_rd, "router_normalization_version", "") or ""
                            ),
                            normalized_text_hash=str(
                                getattr(_rd, "normalized_text_hash", "") or ""
                            ),
                        )
            except Exception:
                pass

        _tools_enabled = getattr(effective_request, "tools_enabled", None)
        _tools_disabled_reason = getattr(
            effective_request, "tools_disabled_reason", None
        )
        try:
            if _rd is not None:
                _cap_id = str(getattr(_rd, "capability_id", "") or "")
                if not _cap_id.strip():
                    _tools_enabled = False
                    _tools_disabled_reason = "SSOT_INVALID_NO_DEFAULT_QA"
        except Exception:
            pass

        _guard_result = {
            "tools_enabled": _tools_enabled,
            "tools_disabled_reason": _tools_disabled_reason,
        }

        mcp_decision = MCPEngine().evaluate(
            intent_tier=_tier,
            intent_type=str(_it) if _it is not None else None,
            router_decision=_rd,
            guard_result=_guard_result,
            had_new_core_entered=False,
            legacy_requested=False,
        )
    except Exception:
        mcp_decision = MCPDecision(
            execution_mode=MCPExecutionMode.TOOL_BLOCKED,
            reason_code="mcp_error",
            capability_id=None,
            intent_tier="UNKNOWN",
            intent_type=None,
        )

    # STAGE_G_DISCOVERY: MCPDecision trace emission callsite (event_type='mcp_decision').
    # NOTE: log_trace_event(...) already calls agent_eyes.emit_event internally.
    # The explicit _eyes_emit('mcp_decision', ...) below is a second emit for the same request.
    # Stage G will lock a single canonical MCPDecision emit; legacy duplicates are tagged.
    try:
        _payload = mcp_decision_to_payload(mcp_decision)
        log_trace_event(
            trace_id=getattr(request, "trace_id", None),
            event_type="mcp_decision",
            payload=_payload,
            client_id=getattr(request, "client_id", None),
            endpoint=endpoint,
        )
    except Exception:
        pass

    _new_core_entered_emitted = False

    executor_only_flag = bool(getattr(request, "executor_only", None))

    def _wrap_iter_with_final_response(source_iter: Iterator[str]) -> Iterator[str]:
        try:
            from app.utils.trace_context import set_current_trace_id

            set_current_trace_id(_trace_id_for_stream)
        except Exception:
            pass

        chunks: list[str] = []
        total_chars = 0
        overflowed = False

        try:
            for chunk in source_iter:
                if not isinstance(chunk, str):
                    try:
                        chunk = str(chunk)
                    except Exception:
                        chunk = ""
                total_chars += len(chunk)
                if total_chars > MAX_BUFFER_CHARS:
                    overflowed = True
                    break
                chunks.append(chunk)
        except Exception as exc:
            _ = exc
            chunks = []

        full_text = "".join(chunks)
        if overflowed:
            try:
                log_trace_event(
                    event_type="validation_error",
                    payload={
                        "error_code": "STAGE10_STREAM_BUFFER_OVERFLOW",
                        "message": "Streaming buffer exceeded MAX_BUFFER_CHARS before completion.",
                        "max_buffer_chars": MAX_BUFFER_CHARS,
                        "seen_chars": total_chars,
                    },
                    client_id=effective_request.client_id,
                    endpoint=endpoint,
                )
                _eyes_emit(
                    "validation_error",
                    {"error_code": "STAGE10_STREAM_BUFFER_OVERFLOW"},
                    client_id=effective_request.client_id,
                    endpoint=endpoint,
                )
            except Exception:
                pass
            full_text = _build_stage10_blocked_reply()

        final_text = _stage10_guard_reply_text(
            reply=full_text,
            endpoint=endpoint,
            client_id=effective_request.client_id,
            executor_only=executor_only_flag,
        )
        final_text = final_text if isinstance(final_text, str) else ""

        try:
            _emit_final_response(
                reply=final_text,
                computed_data=None,
                streaming=True,
                client_id=effective_request.client_id,
                endpoint=endpoint,
            )
        except Exception:
            pass

        yield final_text

    _MAX_CORE_TOOL_ITERATIONS = 4
    _core_last_tool_result: ToolResultEnvelope | None = None
    _core_final_computed_data = None
    _core_final_computed_data_marker: str | None = None
    _core_final_reply_override: str | None = None
    _core_decision = None
    _core_iterations_completed = 0

    for _iter_idx in range(_MAX_CORE_TOOL_ITERATIONS):
        _core_input = OrchestrationInput(
            user_text=last_user_msg or "",
            client_id=getattr(request, "client_id", None),
            session_id=getattr(request, "session_id", None),
            conversation_id=getattr(request, "conversation_id", None),
            trace_id=getattr(request, "trace_id", None),
            feature_flags=_feature_flags,
            request_meta=None,
            state_snapshot=_core_state_snapshot,
            last_tool_result=_core_last_tool_result,
        )
        _core_decision, _core_trace_specs = orchestrate(_core_input, _core_deps)
        _core_iterations_completed = _iter_idx + 1

        _core_decision, _core_trace_specs, _max_iter_triggered = (
            maybe_apply_max_iterations_guard(
                iter_idx=_iter_idx,
                max_iterations=_MAX_CORE_TOOL_ITERATIONS,
                trace_id=getattr(request, "trace_id", None),
                final_text=MAX_ITERATIONS_USER_MESSAGE_HE,
                decision=_core_decision,
                trace_specs=_core_trace_specs,
            )
        )

        _is_legacy_fallback_decision = False
        try:
            _dm = getattr(_core_decision, "debug_meta", None)
            if isinstance(_dm, dict):
                _is_legacy_fallback_decision = bool(_dm.get("legacy_fallback", False))
        except Exception:
            _is_legacy_fallback_decision = False

        if (not _is_legacy_fallback_decision) and (not _new_core_entered_emitted):
            try:
                _nce_payload = {
                    "execution_path": "new_core",
                    "streaming": True,
                    "source": "agent_execution.execute_agent_request",
                }
                log_trace_event(
                    event_type="new_core_entered",
                    payload=_nce_payload,
                    client_id=request.client_id,
                    endpoint=endpoint,
                )
                _eyes_emit(
                    "new_core_entered",
                    _nce_payload,
                    client_id=request.client_id,
                    endpoint=endpoint,
                )
                _new_core_entered_emitted = True
            except Exception:
                pass

        if (
            _iter_idx == 0
            and _new_core_entered_emitted
            and (not _is_legacy_fallback_decision)
        ):
            try:
                _rd = get_router_decision(trace_id=getattr(request, "trace_id", None))
                _cap_id = str(getattr(_rd, "capability_id", "") or "") if _rd else ""
                if not _cap_id.strip():
                    _missing_reason_code = "UNKNOWN"
                    try:
                        if getattr(request, "client_id", None) is None:
                            _missing_reason_code = "MISSING_CLIENT_ID"
                        elif _rd is None or getattr(request, "trace_id", None) is None:
                            if _router_decision_preamble_attempted:
                                _missing_reason_code = "RESOLVER_ERROR"
                            else:
                                _missing_reason_code = "ROUTER_DECISION_NOT_REQUESTED"
                        else:
                            _missing_reason_code = "RESOLVER_ERROR"
                    except Exception:
                        _missing_reason_code = "UNKNOWN"

                    _missing_payload = {
                        "reason": "missing_router_decision_in_new_core",
                        "execution_path": "new_core",
                        "router_decision_missing_reason_code": _missing_reason_code,
                    }
                    log_trace_event(
                        event_type="router_decision_missing",
                        payload=_missing_payload,
                        client_id=request.client_id,
                        endpoint=endpoint,
                    )
                    _eyes_emit(
                        "router_decision_missing",
                        _missing_payload,
                        client_id=request.client_id,
                        endpoint=endpoint,
                    )
            except Exception:
                pass

        if not _is_legacy_fallback_decision:
            try:
                _dc = getattr(_core_decision, "decision_code", None)
                _dc_s = str(getattr(_dc, "value", None) or _dc or "")
                _lp_payload = {
                    "decision_code": _dc_s,
                    "tool_call_requested": _dc == DecisionCode.TOOL_CALL,
                    "tools_requested_count": 1 if _dc == DecisionCode.TOOL_CALL else 0,
                }
                log_trace_event(
                    event_type="loop_policy_evaluated",
                    payload=_lp_payload,
                    client_id=request.client_id,
                    endpoint=endpoint,
                )
                _eyes_emit(
                    "loop_policy_evaluated",
                    _lp_payload,
                    client_id=request.client_id,
                    endpoint=endpoint,
                )
            except Exception:
                pass
        for spec in _core_trace_specs:
            try:
                log_trace_event(
                    trace_id=spec.trace_id,
                    event_type=spec.event_type,
                    payload=spec.payload,
                    client_id=request.client_id,
                    endpoint=endpoint,
                )
                _eyes_emit(
                    spec.event_type,
                    spec.payload,
                    client_id=request.client_id,
                    endpoint=endpoint,
                )
            except Exception:
                pass

        if _max_iter_triggered:
            break

        if getattr(_core_decision, "decision_code", None) != DecisionCode.TOOL_CALL:
            break

        tool_name = getattr(_core_decision, "tool_name", None)
        _core_args = getattr(_core_decision, "tool_args", None)
        tool_args = _core_args if isinstance(_core_args, dict) else {}

        tool_call_id = None
        try:
            tool_call_id = uuid4().hex
        except Exception:
            tool_call_id = None

        tool_result_payload = None

        outcome_final = mcp_decision.outcome_final or MCPOutcomeFinal.TOOL_BLOCKED
        if outcome_final != MCPOutcomeFinal.TOOL_ALLOWED:
            if outcome_final == MCPOutcomeFinal.NO_TOOLS:
                raw = pension_llm_service.chat(
                    list(effective_request.messages or []), effective_request.client_id
                )
                raw = raw if isinstance(raw, str) else ""
                final_text = _stage10_guard_reply_text(
                    reply=raw,
                    endpoint=endpoint,
                    client_id=effective_request.client_id,
                    executor_only=executor_only_flag,
                )
                final_text = final_text if isinstance(final_text, str) else ""
                return StreamingResponse(iter([final_text]), media_type="text/plain")

            if outcome_final == MCPOutcomeFinal.PENDING_APPROVAL:
                reply = (
                    "נדרש אישור כדי לבצע. שלח בקשה חדשה אחרי אישור. "
                    f"reason_code={mcp_decision.reason_code}"
                )
                final_text = _stage10_guard_reply_text(
                    reply=reply,
                    endpoint=endpoint,
                    client_id=effective_request.client_id,
                    executor_only=executor_only_flag,
                )
                final_text = final_text if isinstance(final_text, str) else ""
                return StreamingResponse(iter([final_text]), media_type="text/plain")

            reply = f"הבקשה נחסמה לפי מדיניות. reason_code={mcp_decision.reason_code}"
            final_text = _stage10_guard_reply_text(
                reply=reply,
                endpoint=endpoint,
                client_id=effective_request.client_id,
                executor_only=executor_only_flag,
            )
            final_text = final_text if isinstance(final_text, str) else ""
            return StreamingResponse(iter([final_text]), media_type="text/plain")

        if (
            tool_name == MONTHLY_PENSION_SUMMARY_TOOL_NAME
            and effective_request.client_id is not None
        ):
            # TOOL_EXEC_CALLSITE: execute_with_guard
            raw_tool_result = execute_with_guard(
                request=effective_request,
                db=db,
                tool_name=MONTHLY_PENSION_SUMMARY_TOOL_NAME,
                tool_call_id=tool_call_id,
                tool_args=tool_args,
                streaming=True,
                policy_decision=decision,
                intent_type=intent_type,
                pension_portfolio=getattr(effective_request, "pension_portfolio", None),
                force_max_exemption=False,
                agent_reply=None,
                user_approved=True,
                request_id=None,
            )
            parsed = None
            try:
                parsed = (
                    json.loads(raw_tool_result)
                    if isinstance(raw_tool_result, str)
                    else None
                )
            except Exception:
                parsed = None

            if isinstance(parsed, dict):
                reply = parsed.get("reply")
                computed_data = parsed.get("computed_data")
                marker = parsed.get("computed_data_marker")
                if isinstance(reply, str) and reply.strip():
                    _core_final_reply_override = reply
                if isinstance(computed_data, dict):
                    _core_final_computed_data = computed_data
                if isinstance(marker, str) and marker:
                    _core_final_computed_data_marker = marker
                tool_result_payload = parsed
            else:
                tool_result_payload = raw_tool_result
        elif tool_name == CLIENT_SNAPSHOT_TOOL_NAME:
            # TOOL_EXEC_CALLSITE: execute_with_guard
            raw_tool_result = execute_with_guard(
                request=effective_request,
                db=db,
                tool_name=CLIENT_SNAPSHOT_TOOL_NAME,
                tool_call_id=tool_call_id,
                tool_args=tool_args,
                streaming=True,
                policy_decision=decision,
                intent_type=intent_type,
                pension_portfolio=getattr(effective_request, "pension_portfolio", None),
                force_max_exemption=False,
                agent_reply=None,
                user_approved=True,
                request_id=None,
            )

            parsed = raw_tool_result if isinstance(raw_tool_result, dict) else None
            if isinstance(parsed, dict):
                computed_data = parsed
                _core_final_computed_data = parsed
                reply = (
                    parsed.get("reply")
                    if isinstance(parsed.get("reply"), str)
                    else None
                )
                if isinstance(reply, str) and reply.strip():
                    _core_final_reply_override = reply
                else:
                    status = parsed.get("status")
                    if status == "missing_data":
                        _core_final_reply_override = (
                            "חסרים נתונים להפעלת הכלי. אנא ספק client_id."
                        )
                    elif status == "policy_blocked":
                        _core_final_reply_override = "הבקשה נחסמה לפי מדיניות. נסה לנסח מחדש או לבקש פעולה מותרת."
                    elif status == "schema_error":
                        _core_final_reply_override = (
                            "תקלה במבנה נתוני הכלי. נסה שוב או פנה לתמיכה."
                        )
                    elif status == "budget_exceeded":
                        _core_final_reply_override = (
                            "הבקשה חרגה מתקציב. נסה שוב מאוחר יותר."
                        )
                tool_result_payload = parsed
            else:
                tool_result_payload = raw_tool_result
        elif tool_name == TERMINATION_CONCEPTUAL_NO_EXECUTE_REPLY_TOOL_NAME:
            reply = _TERMINATION_CONCEPTUAL_NO_EXECUTE_STREAM_REPLY
            tool_result_payload = reply
        else:
            break

        _core_last_tool_result = ToolResultEnvelope(
            tool_name=str(tool_name or ""),
            tool_args=tool_args,
            tool_result=tool_result_payload,
            status="ok",
            error_message=None,
            trace_id=getattr(request, "trace_id", None),
            tool_call_id=tool_call_id,
        )

        _core_state_snapshot = enrich_state_snapshot(
            _core_state_snapshot,
            user_text=last_user_msg or "",
            last_tool_result=_core_last_tool_result,
        )
        _core_state_snapshot = apply_tool_result_to_state(
            _core_state_snapshot, _core_last_tool_result
        )

    if (
        _core_decision is not None
        and getattr(_core_decision, "decision_code", None) == DecisionCode.RESPOND_ONLY
    ):
        _final_text = getattr(_core_decision, "final_text", None)
        _final_text_s = _final_text if isinstance(_final_text, str) else ""
        _final_text_s = _final_text_s if _final_text_s.strip() else ""

        reply = ""
        if (
            isinstance(_core_final_reply_override, str)
            and _core_final_reply_override.strip()
        ):
            reply = _core_final_reply_override
        else:
            reply = _final_text_s

        if (reply or "").strip() or _core_final_computed_data is not None:
            if _core_final_computed_data is not None:

                def _gen() -> Iterator[str]:
                    marker = _core_final_computed_data_marker
                    if isinstance(marker, str) and marker:
                        yield marker
                    yield reply

                try:
                    _ep_payload = {"execution_path": "new_core"}
                    log_trace_event(
                        event_type="execution_path_selected",
                        payload=_ep_payload,
                        client_id=effective_request.client_id,
                        endpoint=endpoint,
                    )
                    _eyes_emit(
                        "execution_path_selected",
                        _ep_payload,
                        client_id=effective_request.client_id,
                        endpoint=endpoint,
                    )
                except Exception:
                    pass
                return StreamingResponse(
                    _wrap_iter_with_final_response(_gen()), media_type="text/plain"
                )

            def _core_reply_gen() -> Iterator[str]:
                yield reply

            try:
                _ep_payload = {"execution_path": "new_core"}
                log_trace_event(
                    event_type="execution_path_selected",
                    payload=_ep_payload,
                    client_id=effective_request.client_id,
                    endpoint=endpoint,
                )
                _eyes_emit(
                    "execution_path_selected",
                    _ep_payload,
                    client_id=effective_request.client_id,
                    endpoint=endpoint,
                )
            except Exception:
                pass
            return StreamingResponse(
                _wrap_iter_with_final_response(_core_reply_gen()),
                media_type="text/plain",
            )

        # If we got RESPOND_ONLY but no usable reply/computed_data, allow legacy fallback.

    try:
        _dc = getattr(_core_decision, "decision_code", None)
        _dc_s = str(getattr(_dc, "value", None) or _dc or "")
        _router_decision_guardrails_preamble()
        _legacy_reason_code = "UNKNOWN"
        try:
            _dm = getattr(_core_decision, "debug_meta", None)
            if isinstance(_dm, dict) and bool(_dm.get("legacy_fallback", False)):
                _legacy_reason_code = "CORE_DECISION_REQUESTED_LEGACY"
            elif _MAX_CORE_TOOL_ITERATIONS <= 0:
                _legacy_reason_code = "CORE_LOOP_DISABLED_BY_CONFIG"
        except Exception:
            _legacy_reason_code = "UNKNOWN"
        if _legacy_reason_code not in _LEGACY_REASON_CODES:
            _legacy_reason_code = "UNKNOWN"

        _legacy_payload = {
            "execution_path": "legacy_fallback",
            "legacy_entrypoint": "run_pension_chat_stream",
            "reason": "core_decision_code:" + (_dc_s or "none"),
            "legacy_reason_code": _legacy_reason_code,
            "had_new_core_entered": bool(_new_core_entered_emitted),
            "core_iterations_completed": _core_iterations_completed,
        }
        log_trace_event(
            event_type="legacy_fallback_entered",
            payload=_legacy_payload,
            client_id=effective_request.client_id,
            endpoint=endpoint,
        )
        _eyes_emit(
            "legacy_fallback_entered",
            _legacy_payload,
            client_id=effective_request.client_id,
            endpoint=endpoint,
        )
    except Exception:
        pass

    from app.services.llm_chat.chat_orchestration import (
        run_pension_chat_stream as run_pension_chat_stream_service,
    )

    outcome_final = mcp_decision.outcome_final or MCPOutcomeFinal.TOOL_BLOCKED
    if outcome_final == MCPOutcomeFinal.NO_TOOLS:
        raw = pension_llm_service.chat(
            list(effective_request.messages or []), effective_request.client_id
        )
        raw = raw if isinstance(raw, str) else ""
        final_text = _stage10_guard_reply_text(
            reply=raw,
            endpoint=endpoint,
            client_id=effective_request.client_id,
            executor_only=executor_only_flag,
        )
        final_text = final_text if isinstance(final_text, str) else ""
        return StreamingResponse(iter([final_text]), media_type="text/plain")

    if outcome_final in {
        MCPOutcomeFinal.TOOL_BLOCKED,
        MCPOutcomeFinal.PENDING_APPROVAL,
    }:
        if outcome_final == MCPOutcomeFinal.PENDING_APPROVAL:
            reply = (
                "נדרש אישור משתמש לפני ביצוע פעולה. "
                f"reason_code={mcp_decision.reason_code}"
            )
        else:
            reply = f"הבקשה נחסמה לפי מדיניות. reason_code={mcp_decision.reason_code}"
        final_text = _stage10_guard_reply_text(
            reply=reply,
            endpoint=endpoint,
            client_id=effective_request.client_id,
            executor_only=executor_only_flag,
        )
        final_text = final_text if isinstance(final_text, str) else ""
        return StreamingResponse(iter([final_text]), media_type="text/plain")

    raw_response = run_pension_chat_stream_service(effective_request, db)

    original_body_iterator = raw_response.body_iterator

    async def _traced_stream() -> AsyncIterator[bytes | str]:
        try:
            from app.utils.trace_context import set_current_trace_id

            set_current_trace_id(_trace_id_for_stream)
        except Exception:
            pass

        chunks: list[str] = []
        total_chars = 0
        overflowed = False
        stream_error: BaseException | None = None

        try:
            async for chunk in original_body_iterator:
                try:
                    from app.utils.trace_context import set_current_trace_id

                    set_current_trace_id(_trace_id_for_stream)
                except Exception:
                    pass

                if isinstance(chunk, str):
                    s = chunk
                else:
                    try:
                        s = chunk.decode("utf-8", errors="replace")
                    except Exception:
                        s = ""

                total_chars += len(s)
                if total_chars > MAX_BUFFER_CHARS:
                    overflowed = True
                    break
                chunks.append(s)
        except BaseException as exc:
            stream_error = exc

        if overflowed:
            try:
                log_trace_event(
                    event_type="validation_error",
                    payload={
                        "error_code": "STAGE10_STREAM_BUFFER_OVERFLOW",
                        "message": "Streaming buffer exceeded MAX_BUFFER_CHARS before completion.",
                        "max_buffer_chars": MAX_BUFFER_CHARS,
                        "seen_chars": total_chars,
                    },
                    client_id=effective_request.client_id,
                    endpoint=endpoint,
                )
                _eyes_emit(
                    "validation_error",
                    {"error_code": "STAGE10_STREAM_BUFFER_OVERFLOW"},
                    client_id=effective_request.client_id,
                    endpoint=endpoint,
                )
            except Exception:
                pass
            full_text = _build_stage10_blocked_reply()
        elif stream_error is not None:
            try:
                import traceback as _tb_mod

                _err_payload = {
                    "error_type": type(stream_error).__name__,
                    "error_message": str(stream_error)[:2000],
                    "stack_trace": _tb_mod.format_exc()[:4000],
                    "endpoint": endpoint,
                    "streaming": True,
                }
                log_trace_event(
                    event_type="error",
                    payload=_err_payload,
                    client_id=effective_request.client_id,
                    endpoint=endpoint,
                )
                _eyes_emit(
                    "error",
                    _err_payload,
                    client_id=effective_request.client_id,
                    endpoint=endpoint,
                )
            except Exception:
                pass
            full_text = _build_stage10_blocked_reply()
        else:
            full_text = "".join(chunks)

        final_text = _stage10_guard_reply_text(
            reply=full_text,
            endpoint=endpoint,
            client_id=effective_request.client_id,
            executor_only=executor_only_flag,
        )
        final_text = final_text if isinstance(final_text, str) else ""

        try:
            _ao_payload = {
                "reply_length": len(final_text),
                "reply_preview": final_text[:2000],
                "streaming": True,
            }
            log_trace_event(
                event_type="assistant_output",
                payload=_ao_payload,
                client_id=effective_request.client_id,
                endpoint=endpoint,
            )
            _eyes_emit(
                "assistant_output",
                _ao_payload,
                client_id=effective_request.client_id,
                endpoint=endpoint,
            )
        except Exception:
            pass

        try:
            _emit_final_response(
                reply=final_text,
                computed_data=None,
                streaming=True,
                client_id=effective_request.client_id,
                endpoint=endpoint,
            )
        except Exception:
            pass

        yield final_text

    return StreamingResponse(_traced_stream(), media_type=raw_response.media_type)
