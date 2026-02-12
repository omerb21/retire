"""
Agent Eyes Debug API – trace inspection and management.

Security:
  - Active only when AGENT_EYES_DEBUG_API_ENABLED=1
  - Requires header X-Admin-Token matching env AGENT_EYES_ADMIN_TOKEN
  - Returns 404 when disabled (hides existence of endpoint)
  - Returns 403 on bad/missing token
"""

import json
import os
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.agent_trace_event import AgentTraceEvent

router = APIRouter(prefix="/api/v1/agent-eyes", tags=["agent-eyes-debug"])


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------

def _check_enabled_and_auth(
    x_admin_token: Optional[str] = Header(None),
) -> None:
    """Dependency: verify feature flag + admin token."""
    enabled = (os.getenv("AGENT_EYES_DEBUG_API_ENABLED") or "").strip()
    if enabled != "1":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    expected_token = (os.getenv("AGENT_EYES_ADMIN_TOKEN") or "").strip()
    if not expected_token:
        # Token not configured → refuse access (don't open unauthenticated)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    if not x_admin_token or x_admin_token.strip() != expected_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_to_dict(row: AgentTraceEvent) -> dict[str, Any]:
    payload_parsed: Any = None
    if row.payload_json:
        try:
            payload_parsed = json.loads(row.payload_json)
        except Exception:
            payload_parsed = row.payload_json

    return {
        "id": row.id,
        "event_type": row.event_type,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "client_id": row.client_id,
        "endpoint": row.endpoint,
        "payload_json": payload_parsed,
        "is_truncated": row.is_truncated,
    }


# ---------------------------------------------------------------------------
# A) List recent traces
# ---------------------------------------------------------------------------

@router.get(
    "/traces",
    summary="List recent traces",
    dependencies=[Depends(_check_enabled_and_auth)],
)
def list_traces(
    limit: int = Query(50, ge=1, le=500),
    client_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return distinct trace_ids ordered by most recent event descending."""
    q = db.query(
        AgentTraceEvent.trace_id,
        func.max(AgentTraceEvent.created_at).label("last_event_at"),
        func.count(AgentTraceEvent.id).label("events_count"),
        func.max(AgentTraceEvent.client_id).label("client_id"),
        func.max(AgentTraceEvent.endpoint).label("endpoint"),
    ).filter(
        AgentTraceEvent.trace_id != "unknown",
        AgentTraceEvent.trace_id.isnot(None),
        AgentTraceEvent.trace_id != "",
    )
    if client_id is not None:
        q = q.filter(AgentTraceEvent.client_id == client_id)

    q = (
        q.group_by(AgentTraceEvent.trace_id)
        .order_by(desc("last_event_at"))
        .limit(limit)
    )

    items = []
    for row in q.all():
        items.append({
            "trace_id": row.trace_id,
            "last_event_at": row.last_event_at.isoformat() if row.last_event_at else None,
            "events_count": row.events_count,
            "client_id": row.client_id,
            "endpoint": row.endpoint,
        })

    return {"items": items}


# ---------------------------------------------------------------------------
# B) Get events for a trace
# ---------------------------------------------------------------------------

@router.get(
    "/traces/{trace_id}",
    summary="Get all events for a trace",
    dependencies=[Depends(_check_enabled_and_auth)],
)
def get_trace_events(
    trace_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return all events for *trace_id* in chronological order."""
    events = (
        db.query(AgentTraceEvent)
        .filter(AgentTraceEvent.trace_id == trace_id)
        .order_by(AgentTraceEvent.created_at.asc(), AgentTraceEvent.id.asc())
        .all()
    )
    if not events:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No events found for trace_id '{trace_id}'",
        )

    return {
        "trace_id": trace_id,
        "items": [_row_to_dict(e) for e in events],
    }


# ---------------------------------------------------------------------------
# C) Delete a trace
# ---------------------------------------------------------------------------

@router.delete(
    "/traces/{trace_id}",
    summary="Delete all events for a trace",
    dependencies=[Depends(_check_enabled_and_auth)],
)
def delete_trace(
    trace_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Delete all rows with *trace_id* and return the count."""
    deleted = (
        db.query(AgentTraceEvent)
        .filter(AgentTraceEvent.trace_id == trace_id)
        .delete(synchronize_session="fetch")
    )
    db.commit()
    return {"deleted": deleted}
