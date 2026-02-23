import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.llm_chat import (
    ChatRequest,
    ChatResponse,
    LlmProviderUpdateRequest,
    LlmProviderUpdateResponse,
)
from app.services.agent_execution.execute_agent_request import (
    execute_agent_request,
    execute_agent_request_stream,
)
from app.services.llm_pension_agent_service import pension_llm_service

logger = logging.getLogger("app.llm_chat")
router = APIRouter(prefix="/api/v1/llm", tags=["llm-agent"])


@router.get("/status")
async def get_llm_status() -> dict[str, str | None]:
    """מחזיר מידע על ספק ה-LLM והמודל הפעיל לצורך חיווי ב-UI."""
    return pension_llm_service.get_status()


@router.post("/provider", response_model=LlmProviderUpdateResponse)
async def update_llm_provider(
    payload: LlmProviderUpdateRequest,
) -> LlmProviderUpdateResponse:
    """מחליף ספק/מודל LLM בזמן ריצה ומחזיר את המצב החדש."""
    status = pension_llm_service.set_provider(payload.provider, payload.model_name)
    return LlmProviderUpdateResponse(**status)


@router.post("/pension-chat", response_model=ChatResponse)
async def pension_chat(
    request: ChatRequest, db: Session = Depends(get_db), http_request: Request = None
) -> ChatResponse:
    endpoint = "/api/v1/llm/pension-chat"
    try:
        effective_request = request.model_copy(deep=True)
    except Exception:
        effective_request = request

    try:
        header_val = (
            http_request.headers.get("X-Executor-Only")
            if http_request is not None
            else None
        )
        if header_val is not None:
            object.__setattr__(effective_request, "executor_only", header_val == "1")
    except Exception:
        pass

    try:
        res = execute_agent_request(effective_request, db)

        # emit assistant_output on success
        try:
            from app.services.agent_trace_logger import log_trace_event
            from app.services.agent_eyes.event_collector import emit_event as _eyes_emit

            _ao_payload = {
                "status_code": 200,
                "message_preview": (getattr(res, "reply", "") or "")[:200],
                "streaming": False,
            }
            log_trace_event(
                event_type="assistant_output",
                payload=_ao_payload,
                client_id=request.client_id,
                endpoint=endpoint,
            )
            _eyes_emit(
                "assistant_output",
                _ao_payload,
                client_id=request.client_id,
                endpoint=endpoint,
            )
        except Exception:
            pass

        return res

    except Exception as e:
        # emit assistant_output on failure
        try:
            from app.services.agent_trace_logger import log_trace_event
            from app.services.agent_eyes.event_collector import emit_event as _eyes_emit

            _ao_payload = {
                "status_code": 500,
                "message_preview": "שגיאת מערכת בעת עיבוד הבקשה.",
                "error_type": type(e).__name__,
                "streaming": False,
            }
            log_trace_event(
                event_type="assistant_output",
                payload=_ao_payload,
                client_id=request.client_id,
                endpoint=endpoint,
            )
            _eyes_emit(
                "assistant_output",
                _ao_payload,
                client_id=request.client_id,
                endpoint=endpoint,
            )
        except Exception:
            pass

        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=500,
            content={"detail": "Internal Server Error"},
        )


@router.post("/pension-chat-stream")
async def pension_chat_stream(
    request: ChatRequest, db: Session = Depends(get_db), http_request: Request = None
):
    try:
        effective_request = request.model_copy(deep=True)
    except Exception:
        effective_request = request

    try:
        header_val = (
            http_request.headers.get("X-Executor-Only")
            if http_request is not None
            else None
        )
        if header_val is not None:
            object.__setattr__(effective_request, "executor_only", header_val == "1")
    except Exception:
        pass

    return execute_agent_request_stream(effective_request, db)
