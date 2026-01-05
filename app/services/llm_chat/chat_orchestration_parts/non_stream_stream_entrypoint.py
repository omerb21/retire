from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.schemas.llm_chat import ChatRequest
from app.services.llm_chat.chat_stream_orchestration import (
    run_pension_chat_stream as run_pension_chat_stream_impl,
)


def run_pension_chat_stream(request: ChatRequest, db: Session) -> StreamingResponse:
    return run_pension_chat_stream_impl(request, db)
