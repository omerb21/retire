import os
import json

from datetime import date
import re
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import logging

from app.database import get_db
from app.schemas.llm_chat import (
    ChatRequest,
    ChatResponse,
    ChatMessage,
    LlmProviderUpdateRequest,
    LlmProviderUpdateResponse,
)
from app.services.llm_pension_agent_service import pension_llm_service
from app.services.llm_chat.chat_orchestration import (
    run_pension_chat as run_pension_chat_service,
    run_pension_chat_stream as run_pension_chat_stream_service,
)
from app.services.llm_chat.execution_only_guard import (
    is_execution_only,
    validate_execution_only_output,
    execution_only_blocked,
    get_execution_only_system_prompt,
)
from app.services.llm_chat.execution_only_rewriter import build_exec_only_rewrite_prompt
from app.services.llm_chat.execution_only_fallback import build_execution_only_fallback
from app.services.llm_chat.intent_classifier import ChatIntent, detect_intent
from app.guards.advisor_behavior_guard import enforce_behavioral_limits
from app.guards.tool_intent_guard import (
    allow_tools_for_intent,
    get_tools_disabled_reason,
    is_conceptual_no_execute_request,
    sanitize_words_only_conceptual,
    sanitize_words_only_output,
)
from app.services.agent_trace_logger import log_trace_event
from app.services.agent_eyes.event_collector import emit_event as _eyes_emit
from app.utils.trace_context import get_current_trace_id

logger = logging.getLogger("app.llm_chat")
router = APIRouter(prefix="/api/v1/llm", tags=["llm-agent"])


_EXPLICIT_TOOL_RE = re.compile(r"GET_CLIENT_SNAPSHOT", re.IGNORECASE)

_JSON_ONLY_PHRASES = ("רק json", "json בלבד", "בלי הסברים", "json only", "only json")


def _is_explicit_client_snapshot_request(text: str) -> bool:
    return bool(_EXPLICIT_TOOL_RE.search(text or ""))


def _wants_json_only(text: str) -> bool:
    lowered = (text or "").lower()
    return any(p in lowered for p in _JSON_ONLY_PHRASES)


def _extract_first_json(text: str) -> str | None:
    """Extract the first balanced { ... } JSON block from *text*.

    Returns the JSON string if it parses successfully, else ``None``.
    """
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start : i + 1]
                try:
                    json.loads(candidate)
                    return candidate
                except (json.JSONDecodeError, ValueError):
                    return None
    return None


_HEBREW_RE = re.compile(r"[\u0590-\u05FF]")


def _mojibake_fix_enabled() -> bool:
    raw = (os.getenv("ENABLE_MOJIBAKE_FIX") or "false").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _maybe_fix_hebrew_mojibake(text: str) -> tuple[str, bool]:
    if not isinstance(text, str) or not text:
        return text, False
    if "×" not in text:
        return text, False
    if _HEBREW_RE.search(text):
        return text, False
    if text.count("×") < 3:
        return text, False
    try:
        repaired = text.encode("latin-1").decode("utf-8")
    except Exception:
        return text, False
    if not repaired:
        return text, False
    if not _HEBREW_RE.search(repaired):
        return text, False
    return repaired, (repaired != text)


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


@router.get("/status")
async def get_llm_status() -> dict[str, str | None]:
    """מחזיר מידע על ספק ה-LLM והמודל הפעיל לצורך חיווי ב-UI."""
    return pension_llm_service.get_status()


@router.post("/provider", response_model=LlmProviderUpdateResponse)
async def update_llm_provider(payload: LlmProviderUpdateRequest) -> LlmProviderUpdateResponse:
    """מחליף ספק/מודל LLM בזמן ריצה ומחזיר את המצב החדש."""
    status = pension_llm_service.set_provider(payload.provider, payload.model_name)
    return LlmProviderUpdateResponse(**status)


@router.post("/pension-chat", response_model=ChatResponse)
async def pension_chat(request: ChatRequest, db: Session = Depends(get_db), http_request: Request = None) -> ChatResponse:
    """נקודת קצה לצ'אט עם סוכן ה-LLM הפנסיוני - כולל לולאת הרצה (Execution Loop)."""
    try:
        header_val = None
        if http_request is not None:
            header_val = http_request.headers.get("X-Executor-Only")
        if header_val is not None:
            object.__setattr__(request, "executor_only", header_val == "1")
    except Exception:
        pass

    last_user_msg_for_intent = ""
    try:
        for m in reversed(request.messages or []):
            if getattr(m, "role", None) == "user":
                last_user_msg_for_intent = (getattr(m, "content", "") or "").strip()
                break
    except Exception:
        last_user_msg_for_intent = ""

    try:
        _ui_payload = {
            "user_message": last_user_msg_for_intent,
            "client_id": request.client_id,
            "endpoint": "/api/v1/llm/pension-chat",
            "streaming": False,
            "message_count": len(request.messages or []),
            "body": {"messages_count": len(request.messages or []), "client_id": request.client_id},
        }
        log_trace_event(event_type="user_input", payload=_ui_payload, client_id=request.client_id, endpoint="/api/v1/llm/pension-chat")
        _eyes_emit("user_input", _ui_payload, client_id=request.client_id, endpoint="/api/v1/llm/pension-chat")
    except Exception:
        pass

    trace_id: str | None = None
    try:
        from app.utils.llm_chat_log import get_current_request_id

        trace_id = get_current_request_id()
    except Exception:
        trace_id = None
    if not trace_id and http_request is not None:
        try:
            trace_id = http_request.headers.get("X-Request-Id")
        except Exception:
            trace_id = None

    did_log_mojibake_fix = False

    if _should_compute_monthly_pension(last_user_msg_for_intent) and request.client_id is not None:
        from app.services.pension_chat_compute import compute_monthly_pension_summary

        computed = compute_monthly_pension_summary(db, int(request.client_id), date.today())
        reply = _build_monthly_pension_reply(computed)
        if not isinstance(reply, str) or not reply.strip():
            reply = "Unable to produce monthly pension summary from system."
        if _mojibake_fix_enabled() and isinstance(reply, str):
            fixed, did_fix = _maybe_fix_hebrew_mojibake(reply)
            reply = fixed
            if did_fix and not did_log_mojibake_fix:
                did_log_mojibake_fix = True
                logger.warning("MOJIBAKE_FIX_APPLIED endpoint=pension_chat trace_id=%s", trace_id)
        logger.info("pension_chat reply repr=%r", reply)
        return ChatResponse(reply=reply, computed_data=computed)

    if _is_explicit_client_snapshot_request(last_user_msg_for_intent) and request.client_id is not None:
        try:
            from app.services.llm_chat.tool_handlers.get_client_snapshot import handle_get_client_snapshot
            tool_result = handle_get_client_snapshot(args={}, client_id=int(request.client_id), db=db)
            try:
                log_trace_event(
                    event_type="tool_call",
                    payload={"tool_name": "GET_CLIENT_SNAPSHOT", "args": {}, "shortcut": True},
                    client_id=request.client_id,
                    endpoint="/api/v1/llm/pension-chat",
                )
            except Exception:
                pass
            return ChatResponse(reply=tool_result, computed_data=None)
        except Exception as _snap_exc:
            logger.warning("GET_CLIENT_SNAPSHOT shortcut failed: %s", _snap_exc)

    try:
        if is_execution_only(request) and detect_intent(last_user_msg_for_intent) != ChatIntent.REPORT:
            msgs = list(request.messages or [])
            if not (
                msgs
                and getattr(msgs[0], "role", None) == "system"
                and "מצב: EXECUTION_ONLY" in (getattr(msgs[0], "content", "") or "")
            ):
                msgs.insert(0, ChatMessage(role="system", content=get_execution_only_system_prompt()))
                object.__setattr__(request, "messages", msgs)
    except Exception:
        pass

    try:
        detected_intent = detect_intent(last_user_msg_for_intent)
        tools_enabled = allow_tools_for_intent(last_user_msg_for_intent or "", detected_intent)
        object.__setattr__(request, "tools_enabled", bool(tools_enabled))
        if bool(tools_enabled) is False:
            reason = get_tools_disabled_reason(last_user_msg_for_intent or "", detected_intent)
            if reason is not None:
                object.__setattr__(request, "tools_disabled_reason", reason)
    except Exception:
        pass

    # FLOW A: Conceptual-only hard stop must be early (before any tool/approval pipeline).
    # Apply ONLY when the user explicitly asked not to execute ("בלי לבצע" / "אל תבצע" etc).
    try:
        if (
            (not is_execution_only(request))
            and is_conceptual_no_execute_request(last_user_msg_for_intent)
            and getattr(request, "tools_disabled_reason", None) in {"conceptual", "conceptual_form"}
        ):
            reply = sanitize_words_only_conceptual("", last_user_msg_for_intent)
            allowed, final_text = enforce_behavioral_limits(reply)
            return ChatResponse(reply=final_text if not allowed else reply, computed_data=None)
    except Exception:
        pass

    res = run_pension_chat_service(request, db)
    try:
        logger.info("pension_chat reply repr=%r", getattr(res, "reply", None))
    except Exception:
        pass

    if not isinstance(getattr(res, "reply", None), str) or not (res.reply or "").strip():
        if getattr(res, "computed_data", None) is not None and isinstance(res.computed_data, dict):
            try:
                res.reply = _build_monthly_pension_reply(res.computed_data)
            except Exception:
                res.reply = "🔧 לא התקבלה תשובה מהמערכת. נסה לנסח מחדש."
        else:
            res.reply = "🔧 לא התקבלה תשובה מהמערכת. נסה לנסח מחדש."

    if _mojibake_fix_enabled():
        try:
            if isinstance(res.reply, str):
                fixed, did_fix = _maybe_fix_hebrew_mojibake(res.reply)
                res.reply = fixed
                if did_fix and not did_log_mojibake_fix:
                    did_log_mojibake_fix = True
                    logger.warning("MOJIBAKE_FIX_APPLIED endpoint=pension_chat trace_id=%s", trace_id)
        except Exception:
            pass
    if is_execution_only(request):
        if isinstance(res.reply, str) and "###UI_ACTION###" in res.reply and "###END_UI_ACTION###" in res.reply:
            return res
        try:
            validate_execution_only_output(res.reply)
        except Exception as e:
            last_user_msg = ""
            try:
                for m in reversed(request.messages or []):
                    if getattr(m, "role", None) == "user":
                        last_user_msg = (getattr(m, "content", "") or "").strip()
                        break
            except Exception:
                last_user_msg = ""

            rewritten: str | None = None
            try:
                rewrite_prompt = build_exec_only_rewrite_prompt(res.reply, last_user_msg)
                rewrite_messages = [
                    ChatMessage(role=m["role"], content=m["content"]) for m in rewrite_prompt
                ]
                rewritten = pension_llm_service.chat(rewrite_messages, request.client_id)
                validate_execution_only_output(rewritten)
                return ChatResponse(reply=rewritten, computed_data=res.computed_data)
            except Exception as e2:
                reason = getattr(e2, "reason", getattr(e, "reason", "policy_violation"))
                trace_id = getattr(res, "request_id", None)
                try:
                    from app.utils.llm_chat_log import get_current_request_id

                    trace_id = get_current_request_id() or trace_id
                except Exception:
                    pass
                logger.warning(
                    "EXECUTION_ONLY BLOCKED endpoint=non_stream trace_id=%s reason=%s",
                    trace_id,
                    reason,
                )
                fallback = build_execution_only_fallback(last_user_msg)
                return ChatResponse(reply=fallback, computed_data=None)

    if isinstance(res.reply, str) and "###UI_ACTION###" not in res.reply and "###END_UI_ACTION###" not in res.reply:
        try:
            if bool(getattr(request, "tools_enabled", True)) is False:
                res.reply = sanitize_words_only_output(res.reply)
        except Exception:
            pass

        try:
            if (
                bool(getattr(request, "tools_enabled", True)) is False
                and (not is_execution_only(request))
                and getattr(request, "tools_disabled_reason", None) == "conceptual"
            ):
                res.reply = sanitize_words_only_conceptual(res.reply)
        except Exception:
            pass

        allowed, final_text = enforce_behavioral_limits(res.reply)
        if not allowed:
            return ChatResponse(reply=final_text, computed_data=res.computed_data)

    try:
        if _wants_json_only(last_user_msg_for_intent) and isinstance(res.reply, str):
            extracted = _extract_first_json(res.reply)
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
        log_trace_event(event_type="assistant_output", payload=_ao_payload, client_id=request.client_id, endpoint="/api/v1/llm/pension-chat")
        _eyes_emit("assistant_output", _ao_payload, client_id=request.client_id, endpoint="/api/v1/llm/pension-chat")
    except Exception:
        pass

    return res


@router.post("/pension-chat-stream")
async def pension_chat_stream(request: ChatRequest, db: Session = Depends(get_db), http_request: Request = None):
    """נקודת קצה לצ'אט עם סוכן ה-LLM הפנסיוני בזרימה (streaming).
    
    כרגע תומך רק במחזור אחד (ללא לולאת סוכן מלאה), אך מזהה TOOL_CALL ומריץ אותו.
    """
    try:
        header_val = None
        if http_request is not None:
            header_val = http_request.headers.get("X-Executor-Only")
        if header_val is not None:
            object.__setattr__(request, "executor_only", header_val == "1")
    except Exception:
        pass

    try:
        last_user_msg_for_intent = ""
        for m in reversed(request.messages or []):
            if getattr(m, "role", None) == "user":
                last_user_msg_for_intent = (getattr(m, "content", "") or "").strip()
                break

        try:
            _ui_s_payload = {
                "user_message": last_user_msg_for_intent,
                "client_id": request.client_id,
                "endpoint": "/api/v1/llm/pension-chat-stream",
                "streaming": True,
                "message_count": len(request.messages or []),
                "body": {"messages_count": len(request.messages or []), "client_id": request.client_id},
            }
            log_trace_event(event_type="user_input", payload=_ui_s_payload, client_id=request.client_id, endpoint="/api/v1/llm/pension-chat-stream")
            _eyes_emit("user_input", _ui_s_payload, client_id=request.client_id, endpoint="/api/v1/llm/pension-chat-stream")
        except Exception:
            pass

        if _should_compute_monthly_pension(last_user_msg_for_intent) and request.client_id is not None:
            from app.services.pension_chat_compute import compute_monthly_pension_summary

            computed = compute_monthly_pension_summary(db, int(request.client_id), date.today())
            reply = _build_monthly_pension_reply(computed)
            if not isinstance(reply, str) or not reply.strip():
                reply = "Unable to produce monthly pension summary from system."

            def _gen():
                computed_json = json.dumps(
                    {"type": "computed_data", "data": computed},
                    ensure_ascii=False,
                )
                yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"
                yield reply

            return StreamingResponse(_gen(), media_type="text/plain")
    except Exception:
        pass

    try:
        if "PYTEST_CURRENT_TEST" not in os.environ:
            last_user_msg = ""
            for m in reversed(request.messages or []):
                if getattr(m, "role", None) == "user":
                    last_user_msg = (getattr(m, "content", "") or "").strip()
                    break

            if (not is_execution_only(request)) and last_user_msg.lower() in {"שלום", "היי", "הי", "hello", "hi"}:
                greeting = "שלום! נתחיל כך: אפשר לבקש ניתוח תיק, לבנות תכנית פרישה, או להפיק דוח מסכם."

                def _gen():
                    yield greeting

                return StreamingResponse(_gen(), media_type="text/plain")
    except Exception:
        pass

    try:
        _stream_user_msg = ""
        for m in reversed(request.messages or []):
            if getattr(m, "role", None) == "user":
                _stream_user_msg = (getattr(m, "content", "") or "").strip()
                break
        if _is_explicit_client_snapshot_request(_stream_user_msg) and request.client_id is not None:
            from app.services.llm_chat.tool_handlers.get_client_snapshot import handle_get_client_snapshot
            _snap_result = handle_get_client_snapshot(args={}, client_id=int(request.client_id), db=db)
            try:
                _ep_payload = {"path_id": "chat.stream.explicit_tool_shortcut", "reason": "user_explicitly_requested_GET_CLIENT_SNAPSHOT"}
                log_trace_event(event_type="execution_path", payload=_ep_payload, client_id=request.client_id, endpoint="/api/v1/llm/pension-chat-stream")
                _eyes_emit("execution_path", _ep_payload, client_id=request.client_id, endpoint="/api/v1/llm/pension-chat-stream")

                _tc_payload = {"tool_name": "GET_CLIENT_SNAPSHOT", "args": {}, "client_id": request.client_id, "shortcut": True}
                log_trace_event(event_type="tool_call", payload=_tc_payload, client_id=request.client_id, endpoint="/api/v1/llm/pension-chat-stream")
                _eyes_emit("tool_call", _tc_payload, client_id=request.client_id, endpoint="/api/v1/llm/pension-chat-stream")

                _tr_payload = {"tool_name": "GET_CLIENT_SNAPSHOT", "success": True, "result_preview": (_snap_result or "")[:2000], "result_length": len(_snap_result or ""), "shortcut": True}
                log_trace_event(event_type="tool_result", payload=_tr_payload, client_id=request.client_id, endpoint="/api/v1/llm/pension-chat-stream")
                _eyes_emit("tool_result", _tr_payload, client_id=request.client_id, endpoint="/api/v1/llm/pension-chat-stream")
            except Exception:
                pass

            def _snap_gen():
                yield _snap_result

            return StreamingResponse(_snap_gen(), media_type="text/plain")
    except Exception:
        pass

    raw_response = run_pension_chat_stream_service(request, db)

    # Wrap the streaming response to capture assistant_output trace
    original_body_iterator = raw_response.body_iterator

    async def _traced_stream():
        chunks: list[str] = []
        try:
            async for chunk in original_body_iterator:
                chunks.append(chunk if isinstance(chunk, str) else chunk.decode("utf-8", errors="replace"))
                yield chunk
        except Exception as exc:
            try:
                import traceback as _tb_mod
                _err_payload = {
                    "error_type": type(exc).__name__,
                    "error_message": str(exc)[:2000],
                    "stack_trace": _tb_mod.format_exc()[:4000],
                    "endpoint": "/api/v1/llm/pension-chat-stream",
                    "streaming": True,
                }
                log_trace_event(event_type="error", payload=_err_payload, client_id=request.client_id, endpoint="/api/v1/llm/pension-chat-stream")
                _eyes_emit("error", _err_payload, client_id=request.client_id, endpoint="/api/v1/llm/pension-chat-stream")
            except Exception:
                pass
            raise
        finally:
            try:
                full_text = "".join(chunks)
                _ao_s_payload = {
                    "reply_length": len(full_text),
                    "reply_preview": full_text[:2000],
                    "streaming": True,
                }
                log_trace_event(event_type="assistant_output", payload=_ao_s_payload, client_id=request.client_id, endpoint="/api/v1/llm/pension-chat-stream")
                _eyes_emit("assistant_output", _ao_s_payload, client_id=request.client_id, endpoint="/api/v1/llm/pension-chat-stream")
            except Exception:
                pass

    return StreamingResponse(_traced_stream(), media_type=raw_response.media_type)
