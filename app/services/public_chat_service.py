import math
import os
import secrets
import json
import hmac

from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.public_chat import PublicChatSession, PublicChatMessage
from app.models.scenario import Scenario
from app.schemas.llm_chat import ChatMessage
from app.schemas.public_chat import PublicChatMessageDto
from app.services.client_service import normalize_id_number
from app.services.llm_chat.chat_orchestration import run_pension_chat
from app.schemas.llm_chat import ChatRequest
from app.services.pension_portfolio.snapshot_loader import load_latest_pension_portfolio_snapshot_models


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


def _ensure_client_credit_initialized(client: Client, initial_tokens: int | None = None) -> None:
    if client.public_chat_token_balance is None:
        client.public_chat_token_balance = 0
    if client.public_chat_tokens_spent is None:
        client.public_chat_tokens_spent = 0

    if bool(getattr(client, "public_chat_credit_initialized", False)):
        return

    token_balance = _default_initial_tokens() if initial_tokens is None else max(0, int(initial_tokens))
    client.public_chat_token_balance = int(token_balance)
    client.public_chat_tokens_spent = 0
    client.public_chat_credit_initialized = True


def start_or_get_session(db: Session, id_number: str, initial_tokens: int | None = None) -> PublicChatSession:
    normalized = normalize_id_number(id_number)
    if not normalized:
        raise ValueError("invalid_id_number")

    client = db.query(Client).filter(Client.id_number == normalized).first()
    if not client:
        raise ValueError("client_not_found")

    if not bool(getattr(client, "public_chat_credit_initialized", False)):
        latest_session = (
            db.query(PublicChatSession)
            .filter(PublicChatSession.client_id == client.id)
            .order_by(PublicChatSession.id.desc())
            .first()
        )
        if latest_session is not None:
            client.public_chat_token_balance = int(latest_session.token_balance or 0)
            client.public_chat_tokens_spent = int(latest_session.tokens_spent or 0)
            client.public_chat_credit_initialized = True
        else:
            _ensure_client_credit_initialized(client, initial_tokens=initial_tokens)
    else:
        _ensure_client_credit_initialized(client, initial_tokens=None)
    db.add(client)
    db.commit()
    db.refresh(client)

    existing = (
        db.query(PublicChatSession)
        .filter(PublicChatSession.client_id == client.id)
        .filter(PublicChatSession.is_active.is_(True))
        .order_by(PublicChatSession.id.desc())
        .first()
    )
    if existing:
        desired_balance = int(client.public_chat_token_balance or 0)
        desired_spent = int(client.public_chat_tokens_spent or 0)

        if existing.token_balance != desired_balance or existing.tokens_spent != desired_spent:
            existing.token_balance = desired_balance
            existing.tokens_spent = desired_spent
            db.add(existing)
            db.commit()
            db.refresh(existing)
        return existing

    token_balance = int(client.public_chat_token_balance or 0)
    tokens_spent = int(client.public_chat_tokens_spent or 0)

    session = PublicChatSession(
        session_key=_generate_session_key(),
        client_id=client.id,
        token_balance=token_balance,
        tokens_spent=tokens_spent,
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


def get_session_by_key_with_password(db: Session, session_key: str, password: str | None) -> PublicChatSession:
    session = get_session_by_key(db, session_key)

    client = session.client or db.query(Client).filter(Client.id == session.client_id).first()
    if not client:
        raise ValueError("client_not_found")

    normalized = normalize_id_number(password or "")
    if not normalized or not hmac.compare_digest(normalized, str(client.id_number or "")):
        raise ValueError("invalid_public_chat_password")

    return session


def get_history(db: Session, session: PublicChatSession) -> list[PublicChatMessageDto]:
    rows = (
        db.query(PublicChatMessage)
        .filter(PublicChatMessage.session_id == session.id)
        .order_by(PublicChatMessage.id.asc())
        .all()
    )
    return [
        PublicChatMessageDto(
            role=r.role,
            content=r.content,
            estimated_tokens=int(r.estimated_tokens or 0),
        )
        for r in rows
    ]


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


def _load_latest_pension_portfolio(db: Session, client_id: int) -> tuple[list[dict], str] | None:
    result = load_latest_pension_portfolio_snapshot_models(db, client_id)
    if result is None:
        return None

    portfolio_models, snapshot_at = result
    return [item.model_dump() for item in portfolio_models], snapshot_at


def send_message(db: Session, session: PublicChatSession, user_content: str) -> tuple[str, int]:
    trimmed = (user_content or "").strip()
    if not trimmed:
        raise ValueError("empty_message")

    if not session.is_active:
        raise ValueError("session_inactive")

    client = session.client or db.query(Client).filter(Client.id == session.client_id).first()
    if not client:
        raise ValueError("client_not_found")

    if not bool(getattr(client, "public_chat_credit_initialized", False)):
        client.public_chat_token_balance = int(session.token_balance or 0)
        client.public_chat_tokens_spent = int(session.tokens_spent or 0)
        client.public_chat_credit_initialized = True

    _ensure_client_credit_initialized(client)

    if int(client.public_chat_token_balance or 0) <= 0:
        raise ValueError("tokens_depleted")

    _append_message(db, session, "user", trimmed)

    history = get_history(db, session)
    chat_messages: list[ChatMessage] = [ChatMessage(role=m.role, content=m.content) for m in history]

    pension_portfolio = None
    pension_portfolio_snapshot_at = None
    request = ChatRequest(
        messages=chat_messages,
        client_id=session.client_id,
        pension_portfolio=pension_portfolio,
        pension_portfolio_snapshot_at=pension_portfolio_snapshot_at,
    )
    response = run_pension_chat(request, db)
    reply_text = (response.reply or "").strip()

    _append_message(db, session, "assistant", reply_text)

    tokens_used = _estimate_tokens(trimmed) + _estimate_tokens(reply_text)
    if tokens_used < 0:
        tokens_used = 0

    current_balance = int(client.public_chat_token_balance or 0)
    to_deduct = min(current_balance, int(tokens_used))
    client.public_chat_token_balance = current_balance - to_deduct
    client.public_chat_tokens_spent = int(client.public_chat_tokens_spent or 0) + to_deduct

    session.token_balance = int(client.public_chat_token_balance or 0)
    session.tokens_spent = int(client.public_chat_tokens_spent or 0)

    db.add(client)
    db.add(session)
    db.commit()
    db.refresh(session)

    return reply_text, tokens_used


def top_up(db: Session, session_key: str, tokens: int) -> PublicChatSession:
    if tokens <= 0:
        raise ValueError("invalid_topup")

    session = get_session_by_key(db, session_key)

    client = session.client or db.query(Client).filter(Client.id == session.client_id).first()
    if not client:
        raise ValueError("client_not_found")

    if not bool(getattr(client, "public_chat_credit_initialized", False)):
        client.public_chat_token_balance = int(session.token_balance or 0)
        client.public_chat_tokens_spent = int(session.tokens_spent or 0)
        client.public_chat_credit_initialized = True

    _ensure_client_credit_initialized(client)
    client.public_chat_token_balance = int(client.public_chat_token_balance or 0) + int(tokens)

    session.token_balance = int(client.public_chat_token_balance or 0)
    session.tokens_spent = int(client.public_chat_tokens_spent or 0)

    db.add(client)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session
