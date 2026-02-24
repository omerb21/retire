from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Boolean,
    Text,
    Index,
)
from sqlalchemy.orm import relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PublicChatSession(Base):
    __tablename__ = "public_chat_session"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_key = Column(String(64), nullable=False, unique=True, index=True)

    client_id = Column(Integer, ForeignKey("client.id"), nullable=False, index=True)
    client = relationship("Client")

    token_balance = Column(Integer, nullable=False, default=0)
    tokens_spent = Column(Integer, nullable=False, default=0)

    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    messages = relationship(
        "PublicChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="PublicChatMessage.id",
    )

    __table_args__ = (
        Index("ix_public_chat_session_client_active", "client_id", "is_active"),
    )


class PublicChatMessage(Base):
    __tablename__ = "public_chat_message"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(
        Integer, ForeignKey("public_chat_session.id"), nullable=False, index=True
    )
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)

    estimated_tokens = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    session = relationship("PublicChatSession", back_populates="messages")
