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
    wants_json_only,
)
from app.services.llm_chat.intent_classifier import ChatIntent, detect_intent
from app.services.llm_chat.orchestration_utils_parts.tool_names import (
    MONTHLY_PENSION_SUMMARY_TOOL_NAME,
    TERMINATION_CONCEPTUAL_NO_EXECUTE_REPLY_TOOL_NAME,
)
from app.services.llm_chat.orchestration_core.core_types import OrchestrationDeps, OrchestrationInput
from app.services.llm_chat.orchestration_core.orchestrate import orchestrate
from app.services.llm_chat.orchestration_core.feature_flags import compute_feature_flags
from app.services.llm_chat.orchestration_core.core_types import DecisionCode, ToolResultEnvelope
from app.services.llm_chat.orchestration_core.state_apply import apply_tool_result_to_state
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


_UI_ACTION_RE = re.compile(r"###UI_ACTION###.*?###END_UI_ACTION###", flags=re.DOTALL)
_COMPUTED_DATA_RE = re.compile(r"###COMPUTED_DATA###.*?###END_COMPUTED_DATA###", flags=re.DOTALL)
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


def _stage10_enforce_behavioral_limits(*, text: str, allow_numbers: bool) -> tuple[bool, str]:
    candidate = text or ""

    if not allow_numbers:
        allowed_spans: list[tuple[int, int]] = []
        try:
            allowed_spans.extend(
                [(m.start(), m.end()) for m in _ALLOWED_FORM_SECTION_RE.finditer(candidate)]
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
    *,
    reply: str | None,
    endpoint: str,
    client_id: int | None,
    executor_only: bool,
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
            (
                _COMPUTED_DATA_RE.search(candidate_text)
                or _PENSION_PORTFOLIO_UPDATE_RE.search(candidate_text)
                or _TARGET_PENSION_PLAN_DATA_RE.search(candidate_text)
            )
            and _strip_structured_blocks(candidate_text).strip() == ""
        ):
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
            from app.services.llm_chat.numeric_provenance import build_numeric_match_examples

            examples = build_numeric_match_examples(text=visible_text, window=30, max_examples=3)
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


def _log_policy_decision(*, request: ChatRequest, intent: ChatIntent, decision: PolicyDecision, endpoint: str) -> None:
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
        _eyes_emit("policy_decision", payload, client_id=request.client_id, endpoint=endpoint)
    except Exception:
        pass


def _emit_final_response(*, reply: str | None, computed_data, streaming: bool, client_id: int | None, endpoint: str) -> None:
    try:
        text = reply if isinstance(reply, str) else ""
        stripped = text.lstrip()
        response_kind = "structured_json" if (stripped.startswith("{") and stripped.rstrip().endswith("}")) else "text"
        payload = {
            "response_kind": response_kind,
            "length_chars": len(text),
            "contained_tool_calls": ("###TOOL_CALL###" in text),
            "has_computed_data": computed_data is not None,
            "streaming": bool(streaming),
        }
        log_trace_event(event_type="final_response", payload=payload, client_id=client_id, endpoint=endpoint)
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


def _apply_execution_only_prompt_copy(request: ChatRequest, *, last_user_msg: str, intent: ChatIntent) -> ChatRequest:
    effective = request
    try:
        if is_execution_only(effective) and intent != ChatIntent.REPORT:
            msgs = list(effective.messages or [])
            if not (
                msgs
                and getattr(msgs[0], "role", None) == "system"
                and "מצב: EXECUTION_ONLY" in (getattr(msgs[0], "content", "") or "")
            ):
                msgs.insert(0, ChatMessage(role="system", content=get_execution_only_system_prompt()))
                object.__setattr__(effective, "messages", msgs)
    except Exception:
        pass
    return effective


def _enforce_execution_only_non_stream(
    *,
    request: ChatRequest,
    last_user_msg: str,
    response: ChatResponse,
) -> ChatResponse:
    if not is_execution_only(request):
        return response

    if isinstance(response.reply, str) and "###UI_ACTION###" in response.reply and "###END_UI_ACTION###" in response.reply:
        return response

    try:
        validate_execution_only_output(response.reply)
        return response
    except Exception as e:
        rewritten: str | None = None
        try:
            rewrite_prompt = build_exec_only_rewrite_prompt(response.reply, last_user_msg)
            rewrite_messages = [ChatMessage(role=m["role"], content=m["content"]) for m in rewrite_prompt]
            rewritten = pension_llm_service.chat(rewrite_messages, request.client_id)
            validate_execution_only_output(rewritten)
            return ChatResponse(reply=rewritten, computed_data=response.computed_data)
        except Exception as e2:
            _ = (e, e2)
            fallback = build_execution_only_fallback(last_user_msg)
            return ChatResponse(reply=fallback, computed_data=None)


def _run_execution_only_non_stream(*, request: ChatRequest, last_user_msg: str) -> ChatResponse:
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
            msgs.insert(0, ChatMessage(role="system", content=get_execution_only_system_prompt()))
        object.__setattr__(effective_request, "messages", msgs)
    except Exception:
        pass

    raw = pension_llm_service.chat(list(effective_request.messages or []), effective_request.client_id)
    try:
        validate_execution_only_output(raw)
        return ChatResponse(reply=raw, computed_data=None)
    except Exception as e:
        rewritten: str | None = None
        try:
            rewrite_prompt = build_exec_only_rewrite_prompt(raw, last_user_msg)
            rewrite_messages = [ChatMessage(role=m["role"], content=m["content"]) for m in rewrite_prompt]
            rewritten = pension_llm_service.chat(rewrite_messages, effective_request.client_id)
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
        from app.utils.trace_context import get_current_trace_id, generate_trace_id, set_current_trace_id

        _tid = get_current_trace_id() or generate_trace_id()
        set_current_trace_id(_tid)
        try:
            object.__setattr__(request, "trace_id", _tid)
        except Exception:
            pass
        try:
            if db is not None and hasattr(db, "info") and isinstance(getattr(db, "info", None), dict):
                db.info["trace_id"] = _tid
        except Exception:
            pass
    except Exception:
        pass

    last_user_msg = _find_last_user_message_text(request)
    intent = detect_intent(last_user_msg)

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
        llm_generate=lambda messages, client_id=None: pension_llm_service.chat(messages, client_id),
        policy_gate=decide,
    )
    executor_only_flag = bool(getattr(request, "executor_only", None))

    try:
        _ui_payload = {
            "message_preview": (last_user_msg or "")[:500],
            "streaming": False,
            "executor_only": getattr(request, "executor_only", None),
        }
        log_trace_event(event_type="user_input", payload=_ui_payload, client_id=request.client_id, endpoint=endpoint)
        _eyes_emit("user_input", _ui_payload, client_id=request.client_id, endpoint=endpoint)
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
        log_trace_event(event_type="intent_detected", payload=_it_payload, client_id=request.client_id, endpoint=endpoint)
        _eyes_emit("intent_detected", _it_payload, client_id=request.client_id, endpoint=endpoint)
    except Exception:
        pass

    decision = decide(request=request, intent=intent, allow_write=False)

    _log_policy_decision(request=request, intent=intent, decision=decision, endpoint=endpoint)

    try:
        _mode_payload = {
            "execution_mode": "agent_mode" if bool(decision.tools_allowed) else "qa_mode",
            "tools_allowed": bool(decision.tools_allowed),
            "executor_only": getattr(request, "executor_only", None),
            "streaming": False,
        }
        log_trace_event(event_type="execution_mode", payload=_mode_payload, client_id=request.client_id, endpoint=endpoint)
        _eyes_emit("execution_mode", _mode_payload, client_id=request.client_id, endpoint=endpoint)
    except Exception:
        pass

    effective_request = _apply_tools_policy_copy(
        request,
        last_user_msg=last_user_msg,
        intent=intent,
        policy_tools_allowed=bool(decision.tools_allowed),
    )
    effective_request = _apply_execution_only_prompt_copy(effective_request, last_user_msg=last_user_msg, intent=intent)
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

    _MAX_CORE_TOOL_ITERATIONS = 4
    _core_last_tool_result: ToolResultEnvelope | None = None
    _core_final_computed_data = None
    _core_final_reply_override: str | None = None
    _core_decision = None

    for _iter_idx in range(_MAX_CORE_TOOL_ITERATIONS):
        _core_input = OrchestrationInput(
            user_text=last_user_msg or "",
            client_id=getattr(request, "client_id", None),
            session_id=getattr(request, "session_id", None),
            conversation_id=getattr(request, "conversation_id", None),
            feature_flags=_feature_flags,
            request_meta=None,
            state_snapshot=_core_state_snapshot,
            last_tool_result=_core_last_tool_result,
        )
        _core_decision, _core_trace_specs = orchestrate(_core_input, _core_deps)
        for spec in _core_trace_specs:
            try:
                log_trace_event(
                    event_type=spec.event_type,
                    payload=spec.payload,
                    client_id=request.client_id,
                    endpoint=endpoint,
                )
                _eyes_emit(spec.event_type, spec.payload, client_id=request.client_id, endpoint=endpoint)
            except Exception:
                pass

        if getattr(_core_decision, "decision_code", None) != DecisionCode.TOOL_CALL:
            break

        tool_name = getattr(_core_decision, "tool_name", None)
        _core_args = getattr(_core_decision, "tool_args", None)
        tool_args = _core_args if isinstance(_core_args, dict) else {}

        tool_result_payload = None
        computed_data = None
        if tool_name == "EXECUTION_ONLY":
            _res = _run_execution_only_non_stream(request=request, last_user_msg=last_user_msg)
            tool_result_payload = getattr(_res, "reply", None)
        elif tool_name == MONTHLY_PENSION_SUMMARY_TOOL_NAME and effective_request.client_id is not None:
            from app.services.pension_chat_compute import compute_monthly_pension_summary

            computed_data = compute_monthly_pension_summary(db, int(effective_request.client_id), date.today())
            reply = _build_monthly_pension_reply(computed_data)
            if not isinstance(reply, str) or not reply.strip():
                reply = "Unable to produce monthly pension summary from system."
            _core_final_computed_data = computed_data
            _core_final_reply_override = reply
            tool_result_payload = {"reply": reply, "computed_data": computed_data}
        elif tool_name == CLIENT_SNAPSHOT_TOOL_NAME and effective_request.client_id is not None:
            tool_result_payload = execute_with_guard(
                request=effective_request,
                db=db,
                tool_name=CLIENT_SNAPSHOT_TOOL_NAME,
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
        elif tool_name == TERMINATION_CONCEPTUAL_NO_EXECUTE_REPLY_TOOL_NAME:
            reply = _TERMINATION_CONCEPTUAL_NO_EXECUTE_NON_STREAM_REPLY
            tool_result_payload = reply
        else:
            break

        try:
            tool_call_id = uuid4().hex
        except Exception:
            tool_call_id = None

        _core_last_tool_result = ToolResultEnvelope(
            tool_name=str(tool_name or ""),
            tool_args=tool_args,
            tool_result=tool_result_payload,
            status="ok",
            error_message=None,
            trace_id=getattr(request, "trace_id", None),
            tool_call_id=tool_call_id,
        )

        try:
            if isinstance(_core_state_snapshot, dict) and str(tool_name or "") in {
                "BUILD_TARGET_PENSION_PLAN",
                "RUN_RETIREMENT_CASHFLOW_ANALYSIS",
            }:
                from app.services.llm_chat.chat_orchestration_helpers_parts.tax_autochain import (
                    get_gross_for_tax_chaining,
                )
                from app.services.llm_chat.orchestration_utils_parts.guards_and_validations import (
                    is_net_pension_request,
                )

                _is_net = is_net_pension_request(last_user_msg or "")
                _gross_for_tax = get_gross_for_tax_chaining(
                    is_net=_is_net,
                    tool_name=str(tool_name or ""),
                    tool_result=str(tool_result_payload or ""),
                )
                if _gross_for_tax is not None and _gross_for_tax > 0:
                    _core_state_snapshot["tax_autochain_gross_monthly_pension"] = float(_gross_for_tax)
        except Exception:
            pass
        _core_state_snapshot = apply_tool_result_to_state(_core_state_snapshot, _core_last_tool_result)

    if (
        _core_decision is not None
        and getattr(_core_decision, "decision_code", None) == DecisionCode.RESPOND_ONLY
        and isinstance(getattr(_core_decision, "final_text", None), str)
        and (getattr(_core_decision, "final_text", "") or "").strip()
    ):
        reply = str(getattr(_core_decision, "final_text", ""))
        if isinstance(_core_final_reply_override, str) and _core_final_reply_override.strip():
            reply = _core_final_reply_override
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
        return res

    from app.services.llm_chat.chat_orchestration import run_pension_chat as run_pension_chat_service

    res = run_pension_chat_service(effective_request, db)

    if not isinstance(getattr(res, "reply", None), str) or not (res.reply or "").strip():
        if getattr(res, "computed_data", None) is not None and isinstance(res.computed_data, dict):
            try:
                res.reply = _build_monthly_pension_reply(res.computed_data)
            except Exception:
                res.reply = "🔧 לא התקבלה תשובה מהמערכת. נסה לנסח מחדש."
        else:
            res.reply = "🔧 לא התקבלה תשובה מהמערכת. נסה לנסח מחדש."

    res = _enforce_execution_only_non_stream(request=effective_request, last_user_msg=last_user_msg, response=res)

    if isinstance(res.reply, str) and "###UI_ACTION###" not in res.reply and "###END_UI_ACTION###" not in res.reply:
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
        log_trace_event(event_type="assistant_output", payload=_ao_payload, client_id=effective_request.client_id, endpoint=endpoint)
        _eyes_emit("assistant_output", _ao_payload, client_id=effective_request.client_id, endpoint=endpoint)
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


def execute_agent_request_stream(request: ChatRequest, db: Session) -> StreamingResponse:
    endpoint = "/api/v1/llm/pension-chat-stream"

    try:
        reset_tool_ok_seen()
    except Exception:
        pass

    _trace_id_for_stream = None
    try:
        from app.utils.trace_context import get_current_trace_id, generate_trace_id, set_current_trace_id

        _trace_id_for_stream = get_current_trace_id() or generate_trace_id()
        set_current_trace_id(_trace_id_for_stream)
        try:
            object.__setattr__(request, "trace_id", _trace_id_for_stream)
        except Exception:
            pass
        try:
            if db is not None and hasattr(db, "info") and isinstance(getattr(db, "info", None), dict):
                db.info["trace_id"] = _trace_id_for_stream
        except Exception:
            pass
    except Exception:
        _trace_id_for_stream = None

    last_user_msg = _find_last_user_message_text(request)
    intent = detect_intent(last_user_msg)

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
        llm_generate=lambda messages, client_id=None: pension_llm_service.chat(messages, client_id),
        policy_gate=decide,
    )

    try:
        _ui_payload = {
            "message_preview": (last_user_msg or "")[:500],
            "streaming": True,
            "executor_only": getattr(request, "executor_only", None),
        }
        log_trace_event(event_type="user_input", payload=_ui_payload, client_id=request.client_id, endpoint=endpoint)
        _eyes_emit("user_input", _ui_payload, client_id=request.client_id, endpoint=endpoint)
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
        log_trace_event(event_type="intent_detected", payload=_it_payload, client_id=request.client_id, endpoint=endpoint)
        _eyes_emit("intent_detected", _it_payload, client_id=request.client_id, endpoint=endpoint)
    except Exception:
        pass

    # reuse intent computed earlier
    decision = decide(request=request, intent=intent, allow_write=False)

    _log_policy_decision(request=request, intent=intent, decision=decision, endpoint=endpoint)

    try:
        _mode_payload = {
            "execution_mode": "agent_mode" if bool(decision.tools_allowed) else "qa_mode",
            "tools_allowed": bool(decision.tools_allowed),
            "executor_only": getattr(request, "executor_only", None),
            "streaming": True,
        }
        log_trace_event(event_type="execution_mode", payload=_mode_payload, client_id=request.client_id, endpoint=endpoint)
        _eyes_emit("execution_mode", _mode_payload, client_id=request.client_id, endpoint=endpoint)
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
    _core_final_reply_override: str | None = None
    _core_decision = None

    for _iter_idx in range(_MAX_CORE_TOOL_ITERATIONS):
        _core_input = OrchestrationInput(
            user_text=last_user_msg or "",
            client_id=getattr(request, "client_id", None),
            session_id=getattr(request, "session_id", None),
            conversation_id=getattr(request, "conversation_id", None),
            feature_flags=_feature_flags,
            request_meta=None,
            state_snapshot=_core_state_snapshot,
            last_tool_result=_core_last_tool_result,
        )
        _core_decision, _core_trace_specs = orchestrate(_core_input, _core_deps)
        for spec in _core_trace_specs:
            try:
                log_trace_event(
                    event_type=spec.event_type,
                    payload=spec.payload,
                    client_id=request.client_id,
                    endpoint=endpoint,
                )
                _eyes_emit(spec.event_type, spec.payload, client_id=request.client_id, endpoint=endpoint)
            except Exception:
                pass

        if getattr(_core_decision, "decision_code", None) != DecisionCode.TOOL_CALL:
            break

        tool_name = getattr(_core_decision, "tool_name", None)
        _core_args = getattr(_core_decision, "tool_args", None)
        tool_args = _core_args if isinstance(_core_args, dict) else {}

        tool_result_payload = None
        if tool_name == MONTHLY_PENSION_SUMMARY_TOOL_NAME and effective_request.client_id is not None:
            from app.services.pension_chat_compute import compute_monthly_pension_summary

            computed_data = compute_monthly_pension_summary(db, int(effective_request.client_id), date.today())
            reply = _build_monthly_pension_reply(computed_data)
            if not isinstance(reply, str) or not reply.strip():
                reply = "Unable to produce monthly pension summary from system."
            _core_final_computed_data = computed_data
            _core_final_reply_override = reply
            tool_result_payload = {"reply": reply, "computed_data": computed_data}
        elif tool_name == CLIENT_SNAPSHOT_TOOL_NAME and effective_request.client_id is not None:
            tool_result_payload = execute_with_guard(
                request=effective_request,
                db=db,
                tool_name=CLIENT_SNAPSHOT_TOOL_NAME,
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
        elif tool_name == TERMINATION_CONCEPTUAL_NO_EXECUTE_REPLY_TOOL_NAME:
            reply = _TERMINATION_CONCEPTUAL_NO_EXECUTE_STREAM_REPLY
            tool_result_payload = reply
        else:
            break

        try:
            tool_call_id = uuid4().hex
        except Exception:
            tool_call_id = None

        _core_last_tool_result = ToolResultEnvelope(
            tool_name=str(tool_name or ""),
            tool_args=tool_args,
            tool_result=tool_result_payload,
            status="ok",
            error_message=None,
            trace_id=getattr(request, "trace_id", None),
            tool_call_id=tool_call_id,
        )
        _core_state_snapshot = apply_tool_result_to_state(_core_state_snapshot, _core_last_tool_result)

    if (
        _core_decision is not None
        and getattr(_core_decision, "decision_code", None) == DecisionCode.RESPOND_ONLY
        and isinstance(getattr(_core_decision, "final_text", None), str)
        and (getattr(_core_decision, "final_text", "") or "").strip()
    ):
        reply = str(getattr(_core_decision, "final_text", ""))
        if isinstance(_core_final_reply_override, str) and _core_final_reply_override.strip():
            reply = _core_final_reply_override

        if _core_final_computed_data is not None:
            def _gen() -> Iterator[str]:
                computed_json = json.dumps({"type": "computed_data", "data": _core_final_computed_data}, ensure_ascii=False)
                yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"
                yield reply

            return StreamingResponse(_wrap_iter_with_final_response(_gen()), media_type="text/plain")

        def _core_reply_gen() -> Iterator[str]:
            yield reply

        return StreamingResponse(_wrap_iter_with_final_response(_core_reply_gen()), media_type="text/plain")

    from app.services.llm_chat.chat_orchestration import (
        run_pension_chat_stream as run_pension_chat_stream_service,
    )

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
                log_trace_event(event_type="error", payload=_err_payload, client_id=effective_request.client_id, endpoint=endpoint)
                _eyes_emit("error", _err_payload, client_id=effective_request.client_id, endpoint=endpoint)
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
            log_trace_event(event_type="assistant_output", payload=_ao_payload, client_id=effective_request.client_id, endpoint=endpoint)
            _eyes_emit("assistant_output", _ao_payload, client_id=effective_request.client_id, endpoint=endpoint)
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
