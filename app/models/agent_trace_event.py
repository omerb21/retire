"""
AgentTraceEvent model – stores observability events for Agent Eyes.
Each row is one event in a trace timeline (user_input, llm_request_prepared,
tool_call, tool_result, assistant_output, error).
"""

import json
from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String, Text
from app.database import Base


class AgentTraceEvent(Base):
    __tablename__ = "agent_trace_event"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trace_id = Column(String(64), nullable=False, index=True)
    session_id = Column(String(128), nullable=True, index=True)
    client_id = Column(Integer, nullable=True, index=True)
    endpoint = Column(String(256), nullable=True)
    event_type = Column(String(64), nullable=False, index=True)
    payload_json = Column(Text, nullable=True)
    payload_text = Column(Text, nullable=True)
    is_truncated = Column(Boolean, nullable=False, default=False)
    payload_size = Column(Integer, nullable=True)
    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    __table_args__ = (
        Index("ix_agent_trace_event_trace_created", "trace_id", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<AgentTraceEvent id={self.id} trace_id={self.trace_id!r} "
            f"event_type={self.event_type!r}>"
        )
