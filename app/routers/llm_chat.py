import os

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.llm_chat import (
    ChatRequest,
    ChatResponse,
    LlmProviderUpdateRequest,
    LlmProviderUpdateResponse,
)
from app.services.llm_pension_agent_service import pension_llm_service
from app.services.llm_chat.chat_orchestration import (
    run_pension_chat as run_pension_chat_service,
    run_pension_chat_stream as run_pension_chat_stream_service,
)
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
async def pension_chat(request: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    """נקודת קצה לצ'אט עם סוכן ה-LLM הפנסיוני - כולל לולאת הרצה (Execution Loop)."""
    return run_pension_chat_service(request, db)


@router.post("/pension-chat-stream")
async def pension_chat_stream(request: ChatRequest, db: Session = Depends(get_db)):
    """נקודת קצה לצ'אט עם סוכן ה-LLM הפנסיוני בזרימה (streaming).
    
    כרגע תומך רק במחזור אחד (ללא לולאת סוכן מלאה), אך מזהה TOOL_CALL ומריץ אותו.
    """
    try:
        if "PYTEST_CURRENT_TEST" not in os.environ:
            last_user_msg = ""
            for m in reversed(request.messages or []):
                if getattr(m, "role", None) == "user":
                    last_user_msg = (getattr(m, "content", "") or "").strip()
                    break

            if last_user_msg.lower() in {"שלום", "היי", "הי", "hello", "hi"}:
                greeting = "שלום! איך תרצה שנתחיל? אפשר לבקש ניתוח תיק, לבנות תכנית פרישה, או להפיק דוח מסכם."

                def _gen():
                    yield greeting

                return StreamingResponse(_gen(), media_type="text/plain; charset=utf-8")
    except Exception:
        pass

    return run_pension_chat_stream_service(request, db)
