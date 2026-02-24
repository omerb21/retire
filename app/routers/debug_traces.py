"""
Protected Debug API – Agent Eyes trace viewer.

Endpoints:
    GET  /api/v1/debug/agent-traces          – list recent traces
    GET  /api/v1/debug/agent-traces/{trace_id} – events for one trace
    DELETE /api/v1/debug/agent-traces/{trace_id} – delete events for one trace
    DELETE /api/v1/debug/agent-traces         – purge all events

Protection:
    * Env AGENT_TRACE_DEBUG_ENABLED must be "1" (default off).
    * Header X-Admin-Token must match env AGENT_TRACE_ADMIN_TOKEN (if set).
"""

import json
import os
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.agent_trace_event import AgentTraceEvent

logger = logging.getLogger("app.debug_traces")
router = APIRouter(prefix="/api/v1/debug/agent-traces", tags=["debug-traces"])


def _check_access(x_admin_token: Optional[str] = Header(None)) -> None:
    if os.getenv("AGENT_TRACE_DEBUG_ENABLED", "0") != "1":
        raise HTTPException(status_code=404, detail="Not found")
    expected = (os.getenv("AGENT_TRACE_ADMIN_TOKEN") or "").strip()
    if expected and (x_admin_token or "").strip() != expected:
        raise HTTPException(status_code=403, detail="Forbidden")


@router.get("")
def list_traces(
    limit: int = Query(50, ge=1, le=500),
    client_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    _access: None = Depends(_check_access),
):
    """Return a list of recent distinct traces with summary info."""
    q = db.query(
        AgentTraceEvent.trace_id,
        func.min(AgentTraceEvent.created_at).label("started_at"),
        func.max(AgentTraceEvent.created_at).label("ended_at"),
        func.count(AgentTraceEvent.id).label("event_count"),
        func.min(AgentTraceEvent.client_id).label("client_id"),
        func.min(AgentTraceEvent.endpoint).label("endpoint"),
    ).group_by(AgentTraceEvent.trace_id)

    if client_id is not None:
        q = q.filter(AgentTraceEvent.client_id == client_id)

    q = q.order_by(func.max(AgentTraceEvent.created_at).desc()).limit(limit)

    rows = q.all()
    traces = []
    for r in rows:
        traces.append(
            {
                "trace_id": r.trace_id,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "ended_at": r.ended_at.isoformat() if r.ended_at else None,
                "event_count": r.event_count,
                "client_id": r.client_id,
                "endpoint": r.endpoint,
            }
        )
    return {"traces": traces, "count": len(traces)}


@router.get("/{trace_id}")
def get_trace_events(
    trace_id: str,
    db: Session = Depends(get_db),
    _access: None = Depends(_check_access),
):
    """Return all events for a given trace_id, ordered chronologically."""
    events = (
        db.query(AgentTraceEvent)
        .filter(AgentTraceEvent.trace_id == trace_id)
        .order_by(AgentTraceEvent.created_at.asc(), AgentTraceEvent.id.asc())
        .all()
    )
    result = []
    for ev in events:
        payload = None
        if ev.payload_json:
            try:
                payload = json.loads(ev.payload_json)
            except Exception:
                payload = ev.payload_json
        result.append(
            {
                "id": ev.id,
                "trace_id": ev.trace_id,
                "session_id": ev.session_id,
                "client_id": ev.client_id,
                "endpoint": ev.endpoint,
                "event_type": ev.event_type,
                "payload": payload,
                "payload_text": ev.payload_text,
                "created_at": ev.created_at.isoformat() if ev.created_at else None,
            }
        )
    return {"trace_id": trace_id, "events": result, "count": len(result)}


@router.delete("/{trace_id}")
def delete_trace(
    trace_id: str,
    db: Session = Depends(get_db),
    _access: None = Depends(_check_access),
):
    """Delete all events for a given trace_id."""
    count = (
        db.query(AgentTraceEvent)
        .filter(AgentTraceEvent.trace_id == trace_id)
        .delete(synchronize_session=False)
    )
    db.commit()
    return {"deleted": count, "trace_id": trace_id}


@router.delete("")
def purge_all(
    db: Session = Depends(get_db),
    _access: None = Depends(_check_access),
):
    """Purge ALL trace events. Use with caution."""
    count = db.query(AgentTraceEvent).delete(synchronize_session=False)
    db.commit()
    return {"deleted": count}
