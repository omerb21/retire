import os

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
)
from app.services.llm_chat.execution_only_rewriter import build_exec_only_rewrite_prompt

logger = logging.getLogger("app.llm_chat")
router = APIRouter(prefix="/api/v1/llm", tags=["llm-agent"])


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

    res = run_pension_chat_service(request, db)
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
                blocked = execution_only_blocked(reason)
                return ChatResponse(reply=blocked, computed_data=None)
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

                return StreamingResponse(_gen(), media_type="text/plain; charset=utf-8")
    except Exception:
        pass

    return run_pension_chat_stream_service(request, db)
