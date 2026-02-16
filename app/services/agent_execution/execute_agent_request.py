import json
import logging
import os
from datetime import date
from typing import AsyncIterator, Iterator

from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.guards.advisor_behavior_guard import enforce_behavioral_limits
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
    extract_first_json,
    is_explicit_client_snapshot_request,
    wants_json_only,
)
from app.services.llm_chat.intent_classifier import ChatIntent, detect_intent
from app.services.intent_classifier import IntentType, classify_intent
from app.services.llm_pension_agent_service import pension_llm_service

logger = logging.getLogger("app.llm_chat")


def _find_last_user_message_text(request: ChatRequest) -> str:
    try:
        for m in reversed(request.messages or []):
            if getattr(m, "role", None) == "user":
                return (getattr(m, "content", "") or "").strip()
    except Exception:
        return ""
    return ""


def _should_compute_monthly_pension(user_text: str) -> bool:
    normalized = (user_text or "").strip()
    if not normalized:
        return False
    lowered = normalized.lower()
    return (
        ("monthly_pension" in lowered)
        or ("קצבה חודשית" in normalized)
        or ("קצבה נוכחית" in normalized)
    )


def _build_monthly_pension_reply(payload: dict) -> str:
    try:
        client_id = int(payload.get("client_id") or 0)
    except Exception:
        client_id = 0
    mp = payload.get("monthly_pension") if isinstance(payload.get("monthly_pension"), dict) else {}
    current = mp.get("current") if isinstance(mp.get("current"), dict) else {}
    future = mp.get("future") if isinstance(mp.get("future"), dict) else {}
    taxable = current.get("taxable") if isinstance(current.get("taxable"), dict) else {}
    exempt = current.get("exempt") if isinstance(current.get("exempt"), dict) else {}

    def _i(v: object) -> int:
        try:
            return int(v or 0)
        except Exception:
            return 0

    def _f(v: object) -> float:
        try:
            return float(v or 0)
        except Exception:
            return 0.0

    cur_count = _i(current.get("count"))
    cur_sum = _f(current.get("sum"))
    fut_count = _i(future.get("count"))
    fut_sum = _f(future.get("sum"))
    taxable_sum = _f(taxable.get("sum"))
    exempt_sum = _f(exempt.get("sum"))

    return (
        f"Monthly pension summary for client {client_id}: "
        f"current_count={cur_count}, current_sum={cur_sum:,.2f}; "
        f"taxable_sum={taxable_sum:,.2f}, exempt_sum={exempt_sum:,.2f}; "
        f"future_count={fut_count}, future_sum={fut_sum:,.2f}."
    )


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

    last_user_msg = _find_last_user_message_text(request)

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

    intent = detect_intent(last_user_msg)

    if is_execution_only(request) and intent != ChatIntent.REPORT:
        return _run_execution_only_non_stream(request=request, last_user_msg=last_user_msg)

    decision = decide(request=request, intent=intent, allow_write=False)

    _log_policy_decision(request=request, intent=intent, decision=decision, endpoint=endpoint)

    effective_request = _apply_tools_policy_copy(
        request,
        last_user_msg=last_user_msg,
        intent=intent,
        policy_tools_allowed=bool(decision.tools_allowed),
    )
    effective_request = _apply_execution_only_prompt_copy(effective_request, last_user_msg=last_user_msg, intent=intent)

    try:
        _ui_payload = {
            "user_message": last_user_msg,
            "client_id": effective_request.client_id,
            "endpoint": endpoint,
            "streaming": False,
            "message_count": len(effective_request.messages or []),
            "body": {
                "messages_count": len(effective_request.messages or []),
                "client_id": effective_request.client_id,
            },
        }
        log_trace_event(event_type="user_input", payload=_ui_payload, client_id=effective_request.client_id, endpoint=endpoint)
        _eyes_emit("user_input", _ui_payload, client_id=effective_request.client_id, endpoint=endpoint)
    except Exception:
        pass

    if _should_compute_monthly_pension(last_user_msg) and effective_request.client_id is not None:
        from app.services.pension_chat_compute import compute_monthly_pension_summary

        computed = compute_monthly_pension_summary(db, int(effective_request.client_id), date.today())
        reply = _build_monthly_pension_reply(computed)
        if not isinstance(reply, str) or not reply.strip():
            reply = "Unable to produce monthly pension summary from system."
        return ChatResponse(reply=reply, computed_data=computed)

    if is_explicit_client_snapshot_request(last_user_msg) and effective_request.client_id is not None:
        try:
            from app.services.llm_chat.tool_handlers.get_client_snapshot import handle_get_client_snapshot

            tool_result = handle_get_client_snapshot(args={}, client_id=int(effective_request.client_id), db=db)
            try:
                log_trace_event(
                    event_type="tool_call",
                    payload={"tool_name": "GET_CLIENT_SNAPSHOT", "args": {}, "shortcut": True},
                    client_id=effective_request.client_id,
                    endpoint=endpoint,
                )
                _eyes_emit(
                    "tool_call",
                    {"tool_name": "GET_CLIENT_SNAPSHOT", "args": {}, "shortcut": True},
                    client_id=effective_request.client_id,
                    endpoint=endpoint,
                )
            except Exception:
                pass
            return ChatResponse(reply=tool_result, computed_data=None)
        except Exception as exc:
            logger.warning("GET_CLIENT_SNAPSHOT deterministic lane failed: %s", exc)

    try:
        if (
            (not is_execution_only(effective_request))
            and is_conceptual_no_execute_request(last_user_msg)
            and getattr(effective_request, "tools_disabled_reason", None) in {"conceptual", "conceptual_form"}
        ):
            reply = sanitize_words_only_conceptual("", last_user_msg)
            allowed, final_text = enforce_behavioral_limits(reply)
            return ChatResponse(reply=final_text if not allowed else reply, computed_data=None)
    except Exception:
        pass

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

        allowed, final_text = enforce_behavioral_limits(res.reply)
        if not allowed:
            return ChatResponse(reply=final_text, computed_data=res.computed_data)

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

    return res


def execute_agent_request_stream(request: ChatRequest, db: Session) -> StreamingResponse:
    endpoint = "/api/v1/llm/pension-chat-stream"

    last_user_msg = _find_last_user_message_text(request)

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

    intent = detect_intent(last_user_msg)
    decision = decide(request=request, intent=intent, allow_write=False)

    _log_policy_decision(request=request, intent=intent, decision=decision, endpoint=endpoint)

    effective_request = _apply_tools_policy_copy(
        request,
        last_user_msg=last_user_msg,
        intent=intent,
        policy_tools_allowed=bool(decision.tools_allowed),
    )

    try:
        _ui_payload = {
            "user_message": last_user_msg,
            "client_id": effective_request.client_id,
            "endpoint": endpoint,
            "streaming": True,
            "message_count": len(effective_request.messages or []),
            "body": {
                "messages_count": len(effective_request.messages or []),
                "client_id": effective_request.client_id,
            },
        }
        log_trace_event(event_type="user_input", payload=_ui_payload, client_id=effective_request.client_id, endpoint=endpoint)
        _eyes_emit("user_input", _ui_payload, client_id=effective_request.client_id, endpoint=endpoint)
    except Exception:
        pass

    if _should_compute_monthly_pension(last_user_msg) and effective_request.client_id is not None:
        from app.services.pension_chat_compute import compute_monthly_pension_summary

        computed = compute_monthly_pension_summary(db, int(effective_request.client_id), date.today())
        reply = _build_monthly_pension_reply(computed)
        if not isinstance(reply, str) or not reply.strip():
            reply = "Unable to produce monthly pension summary from system."

        def _gen() -> Iterator[str]:
            computed_json = json.dumps({"type": "computed_data", "data": computed}, ensure_ascii=False)
            yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"
            yield reply

        return StreamingResponse(_gen(), media_type="text/plain")

    if is_explicit_client_snapshot_request(last_user_msg) and effective_request.client_id is not None:
        from app.services.llm_chat.tool_handlers.get_client_snapshot import handle_get_client_snapshot

        snap_result = handle_get_client_snapshot(args={}, client_id=int(effective_request.client_id), db=db)
        try:
            _ep_payload = {
                "path_id": "chat.stream.explicit_tool_shortcut",
                "reason": "user_explicitly_requested_GET_CLIENT_SNAPSHOT",
            }
            log_trace_event(event_type="execution_path", payload=_ep_payload, client_id=effective_request.client_id, endpoint=endpoint)
            _eyes_emit("execution_path", _ep_payload, client_id=effective_request.client_id, endpoint=endpoint)

            _tc_payload = {
                "tool_name": "GET_CLIENT_SNAPSHOT",
                "args": {},
                "client_id": effective_request.client_id,
                "shortcut": True,
            }
            log_trace_event(event_type="tool_call", payload=_tc_payload, client_id=effective_request.client_id, endpoint=endpoint)
            _eyes_emit("tool_call", _tc_payload, client_id=effective_request.client_id, endpoint=endpoint)

            _tr_payload = {
                "tool_name": "GET_CLIENT_SNAPSHOT",
                "success": True,
                "result_preview": (snap_result or "")[:2000],
                "result_length": len(snap_result or ""),
                "shortcut": True,
            }
            log_trace_event(event_type="tool_result", payload=_tr_payload, client_id=effective_request.client_id, endpoint=endpoint)
            _eyes_emit("tool_result", _tr_payload, client_id=effective_request.client_id, endpoint=endpoint)
        except Exception:
            pass

        def _snap_gen() -> Iterator[str]:
            yield snap_result

        return StreamingResponse(_snap_gen(), media_type="text/plain")

    if "PYTEST_CURRENT_TEST" not in os.environ:
        try:
            if (not is_execution_only(effective_request)) and (last_user_msg.lower() in {"שלום", "היי", "הי", "hello", "hi"}):
                greeting = "שלום! נתחיל כך: אפשר לבקש ניתוח תיק, לבנות תכנית פרישה, או להפיק דוח מסכם."

                def _greet_gen() -> Iterator[str]:
                    yield greeting

                return StreamingResponse(_greet_gen(), media_type="text/plain")
        except Exception:
            pass

    from app.services.llm_chat.chat_orchestration import (
        run_pension_chat_stream as run_pension_chat_stream_service,
    )

    raw_response = run_pension_chat_stream_service(effective_request, db)

    original_body_iterator = raw_response.body_iterator

    async def _traced_stream() -> AsyncIterator[bytes | str]:
        chunks: list[str] = []
        try:
            async for chunk in original_body_iterator:
                if isinstance(chunk, str):
                    chunks.append(chunk)
                else:
                    chunks.append(chunk.decode("utf-8", errors="replace"))
                yield chunk
        except Exception as exc:
            try:
                import traceback as _tb_mod

                _err_payload = {
                    "error_type": type(exc).__name__,
                    "error_message": str(exc)[:2000],
                    "stack_trace": _tb_mod.format_exc()[:4000],
                    "endpoint": endpoint,
                    "streaming": True,
                }
                log_trace_event(event_type="error", payload=_err_payload, client_id=effective_request.client_id, endpoint=endpoint)
                _eyes_emit("error", _err_payload, client_id=effective_request.client_id, endpoint=endpoint)
            except Exception:
                pass
            raise
        finally:
            try:
                full_text = "".join(chunks)
                _ao_payload = {
                    "reply_length": len(full_text),
                    "reply_preview": full_text[:2000],
                    "streaming": True,
                }
                log_trace_event(event_type="assistant_output", payload=_ao_payload, client_id=effective_request.client_id, endpoint=endpoint)
                _eyes_emit("assistant_output", _ao_payload, client_id=effective_request.client_id, endpoint=endpoint)
            except Exception:
                pass

    return StreamingResponse(_traced_stream(), media_type=raw_response.media_type)
