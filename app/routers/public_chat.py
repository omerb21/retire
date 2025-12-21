from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.public_chat import (
    PublicChatStartRequest,
    PublicChatStartResponse,
    PublicChatStatusResponse,
    PublicChatHistoryResponse,
    PublicChatSendMessageRequest,
    PublicChatSendMessageResponse,
    PublicChatTopUpRequest,
    PublicChatTopUpResponse,
)
from app.services.public_chat_service import (
    start_or_get_session,
    get_session_by_key,
    get_session_by_key_with_password,
    get_history,
    send_message,
    top_up,
)
from app.services.llm_pension_agent_service import pension_llm_service


router = APIRouter(prefix="/api/v1/public-chat", tags=["public-chat"])


@router.post("/start", response_model=PublicChatStartResponse)
def start_public_chat(payload: PublicChatStartRequest, db: Session = Depends(get_db)) -> PublicChatStartResponse:
    try:
        session = start_or_get_session(db, payload.id_number, payload.initial_tokens)
        client_name = session.client.full_name if session.client else None
        llm_status = pension_llm_service.get_status()
        return PublicChatStartResponse(
            session_key=session.session_key,
            client_id=session.client_id,
            client_name=client_name,
            token_balance=session.token_balance,
            llm_provider=llm_status.get("provider"),
            llm_backend=llm_status.get("backend"),
            llm_model_name=llm_status.get("model_name"),
        )
    except ValueError as e:
        if str(e) == "client_not_found":
            raise HTTPException(status_code=404, detail="Client not found")
        if str(e) == "invalid_id_number":
            raise HTTPException(status_code=400, detail="Invalid id_number")
        raise


@router.get("/sessions/{session_key}/status", response_model=PublicChatStatusResponse)
def get_public_chat_status(
    session_key: str,
    db: Session = Depends(get_db),
    x_public_chat_password: str | None = Header(default=None, alias="X-Public-Chat-Password"),
) -> PublicChatStatusResponse:
    try:
        session = get_session_by_key_with_password(db, session_key, x_public_chat_password)
        client_name = session.client.full_name if session.client else None
        llm_status = pension_llm_service.get_status()
        return PublicChatStatusResponse(
            session_key=session.session_key,
            client_id=session.client_id,
            client_name=client_name,
            token_balance=session.token_balance,
            tokens_spent=session.tokens_spent,
            is_active=session.is_active,
            llm_provider=llm_status.get("provider"),
            llm_backend=llm_status.get("backend"),
            llm_model_name=llm_status.get("model_name"),
        )
    except ValueError as e:
        if str(e) == "session_not_found":
            raise HTTPException(status_code=404, detail="Session not found")
        if str(e) == "invalid_public_chat_password":
            raise HTTPException(status_code=401, detail="Invalid public chat password")
        raise


@router.get("/sessions/{session_key}/history", response_model=PublicChatHistoryResponse)
def get_public_chat_history(
    session_key: str,
    db: Session = Depends(get_db),
    x_public_chat_password: str | None = Header(default=None, alias="X-Public-Chat-Password"),
) -> PublicChatHistoryResponse:
    try:
        session = get_session_by_key_with_password(db, session_key, x_public_chat_password)
        messages = get_history(db, session)
        return PublicChatHistoryResponse(session_key=session.session_key, messages=messages)
    except ValueError as e:
        if str(e) == "session_not_found":
            raise HTTPException(status_code=404, detail="Session not found")
        if str(e) == "invalid_public_chat_password":
            raise HTTPException(status_code=401, detail="Invalid public chat password")
        raise


@router.post("/sessions/{session_key}/messages", response_model=PublicChatSendMessageResponse)
def send_public_chat_message(
    session_key: str,
    payload: PublicChatSendMessageRequest,
    db: Session = Depends(get_db),
    x_public_chat_password: str | None = Header(default=None, alias="X-Public-Chat-Password"),
) -> PublicChatSendMessageResponse:
    try:
        session = get_session_by_key_with_password(db, session_key, x_public_chat_password)
        reply, tokens_used = send_message(db, session, payload.content)
        refreshed = get_session_by_key(db, session_key)
        return PublicChatSendMessageResponse(
            reply=reply,
            token_balance=refreshed.token_balance,
            tokens_spent=refreshed.tokens_spent,
            tokens_used=tokens_used,
            depleted=refreshed.token_balance <= 0,
        )
    except ValueError as e:
        msg = str(e)
        if msg == "session_not_found":
            raise HTTPException(status_code=404, detail="Session not found")
        if msg == "invalid_public_chat_password":
            raise HTTPException(status_code=401, detail="Invalid public chat password")
        if msg == "tokens_depleted":
            raise HTTPException(status_code=402, detail="Token credits depleted")
        if msg == "session_inactive":
            raise HTTPException(status_code=403, detail="Session is inactive")
        if msg == "empty_message":
            raise HTTPException(status_code=400, detail="Empty message")
        raise


@router.post("/topup", response_model=PublicChatTopUpResponse)
def topup_public_chat(payload: PublicChatTopUpRequest, db: Session = Depends(get_db)) -> PublicChatTopUpResponse:
    try:
        session = top_up(db, payload.session_key, payload.tokens)
        return PublicChatTopUpResponse(
            session_key=session.session_key,
            token_balance=session.token_balance,
            tokens_spent=session.tokens_spent,
        )
    except ValueError as e:
        msg = str(e)
        if msg == "session_not_found":
            raise HTTPException(status_code=404, detail="Session not found")
        if msg == "invalid_topup":
            raise HTTPException(status_code=400, detail="Invalid top-up")
        raise
