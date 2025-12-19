import math
import os
import secrets

from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.public_chat import PublicChatSession, PublicChatMessage
from app.schemas.llm_chat import ChatMessage
from app.schemas.public_chat import PublicChatMessageDto
from app.services.client_service import normalize_id_number
from app.services.llm_chat.chat_orchestration import run_pension_chat
from app.schemas.llm_chat import ChatRequest


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return int(math.ceil(len(text) / 4))


def _generate_session_key() -> str:
    return secrets.token_urlsafe(32)


def _default_initial_tokens() -> int:
    raw = os.getenv("PUBLIC_CHAT_INITIAL_TOKENS", "5000")
    try:
        value = int(raw)
        return max(0, value)
    except Exception:
        return 5000


def start_or_get_session(db: Session, id_number: str, initial_tokens: int | None = None) -> PublicChatSession:
    normalized = normalize_id_number(id_number)
    if not normalized:
        raise ValueError("invalid_id_number")

    client = db.query(Client).filter(Client.id_number == normalized).first()
    if not client:
        raise ValueError("client_not_found")

    existing = (
        db.query(PublicChatSession)
        .filter(PublicChatSession.client_id == client.id)
        .filter(PublicChatSession.is_active.is_(True))
        .order_by(PublicChatSession.id.desc())
        .first()
    )
    if existing:
        return existing

    token_balance = _default_initial_tokens() if initial_tokens is None else max(0, int(initial_tokens))

    session = PublicChatSession(
        session_key=_generate_session_key(),
        client_id=client.id,
        token_balance=token_balance,
        tokens_spent=0,
        is_active=True,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_session_by_key(db: Session, session_key: str) -> PublicChatSession:
    session = db.query(PublicChatSession).filter(PublicChatSession.session_key == session_key).first()
    if not session:
        raise ValueError("session_not_found")
    return session


def get_history(db: Session, session: PublicChatSession) -> list[PublicChatMessageDto]:
    rows = (
        db.query(PublicChatMessage)
        .filter(PublicChatMessage.session_id == session.id)
        .order_by(PublicChatMessage.id.asc())
        .all()
    )
    return [PublicChatMessageDto(role=r.role, content=r.content) for r in rows]


def _append_message(db: Session, session: PublicChatSession, role: str, content: str) -> PublicChatMessage:
    msg = PublicChatMessage(
        session_id=session.id,
        role=role,
        content=content,
        estimated_tokens=_estimate_tokens(content),
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def send_message(db: Session, session: PublicChatSession, user_content: str) -> tuple[str, int]:
    trimmed = (user_content or "").strip()
    if not trimmed:
        raise ValueError("empty_message")

    if not session.is_active:
        raise ValueError("session_inactive")

    if session.token_balance <= 0:
        raise ValueError("tokens_depleted")

    _append_message(db, session, "user", trimmed)

    history = get_history(db, session)
    chat_messages: list[ChatMessage] = [ChatMessage(role=m.role, content=m.content) for m in history]

    request = ChatRequest(messages=chat_messages, client_id=session.client_id)
    response = run_pension_chat(request, db)
    reply_text = (response.reply or "").strip()

    _append_message(db, session, "assistant", reply_text)

    tokens_used = _estimate_tokens(trimmed) + _estimate_tokens(reply_text)
    if tokens_used < 0:
        tokens_used = 0

    to_deduct = min(session.token_balance, tokens_used)
    session.token_balance -= to_deduct
    session.tokens_spent += to_deduct
    db.add(session)
    db.commit()
    db.refresh(session)

    return reply_text, tokens_used


def top_up(db: Session, session_key: str, tokens: int) -> PublicChatSession:
    print(f"[DEBUG] Top up called with session_key={session_key}, tokens={tokens}")
    session = get_session_by_key(db, session_key)
    if not session:
        print(f"[ERROR] Session {session_key} not found")
        raise ValueError("session_not_found")
    if tokens <= 0:
        print(f"[ERROR] Invalid token amount: {tokens}")
        raise ValueError("invalid_topup")
    
    print(f"[DEBUG] Current balance: {session.token_balance}, adding {tokens} tokens")
    session.token_balance += tokens
    db.commit()
    db.refresh(session)
    print(f"[DEBUG] New balance: {session.token_balance}")
    return session
