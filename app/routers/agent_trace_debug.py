"""
Debug API for Agent Eyes trace inspection.

Security:
  - Active only when AGENT_TRACE_DEBUG_ENABLED=1
  - Requires header X-Admin-Token matching env ADMIN_DEBUG_TOKEN
  - Returns 404 when disabled, 401 on bad/missing token
"""

import json
import os
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.agent_trace_event import AgentTraceEvent

router = APIRouter(prefix="/api/v1/debug", tags=["agent-trace-debug"])


def _check_enabled_and_auth(
    x_admin_token: Optional[str] = Header(None),
) -> None:
    """Dependency: verify feature flag + admin token."""
    enabled = (os.getenv("AGENT_TRACE_DEBUG_ENABLED") or "").strip()
    if enabled != "1":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    expected_token = (os.getenv("ADMIN_DEBUG_TOKEN") or "").strip()
    if not expected_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin token not configured")

    if not x_admin_token or x_admin_token.strip() != expected_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin token")


def _row_to_dict(row: AgentTraceEvent) -> dict[str, Any]:
    payload_parsed: Any = None
    if row.payload_json:
        try:
            payload_parsed = json.loads(row.payload_json)
        except Exception:
            payload_parsed = row.payload_json

    return {
        "id": row.id,
        "trace_id": row.trace_id,
        "session_id": row.session_id,
        "client_id": row.client_id,
        "endpoint": row.endpoint,
        "event_type": row.event_type,
        "payload": payload_parsed,
        "payload_text": row.payload_text,
        "is_truncated": row.is_truncated,
        "payload_size": row.payload_size,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.get(
    "/traces",
    summary="List recent trace IDs",
    dependencies=[Depends(_check_enabled_and_auth)],
)
def list_traces(
    limit: int = Query(50, ge=1, le=500),
    client_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
) -> List[dict[str, Any]]:
    """Return distinct trace_ids ordered by most recent event, with timestamps."""
    q = db.query(
        AgentTraceEvent.trace_id,
        func.min(AgentTraceEvent.created_at).label("first_event"),
        func.max(AgentTraceEvent.created_at).label("last_event"),
        func.count(AgentTraceEvent.id).label("event_count"),
    )
    if client_id is not None:
        q = q.filter(AgentTraceEvent.client_id == client_id)
    q = q.group_by(AgentTraceEvent.trace_id).order_by(desc("last_event")).limit(limit)

    results = []
    for row in q.all():
        results.append({
            "trace_id": row.trace_id,
            "first_event": row.first_event.isoformat() if row.first_event else None,
            "last_event": row.last_event.isoformat() if row.last_event else None,
            "event_count": row.event_count,
        })
    return results


@router.get(
    "/traces/{trace_id}",
    summary="Get all events for a trace",
    dependencies=[Depends(_check_enabled_and_auth)],
)
def get_trace_events(
    trace_id: str,
    db: Session = Depends(get_db),
) -> List[dict[str, Any]]:
    """Return all events for a given trace_id in chronological order."""
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
    return [_row_to_dict(e) for e in events]


# ---------------------------------------------------------------------------
# Trace Fixtures – run a minimal operation to produce a full trace chain
# ---------------------------------------------------------------------------

_VALID_FIXTURES = {"cashflow", "target_plan", "termination"}


@router.post(
    "/trace-fixtures/run",
    summary="Run a trace fixture to generate a full event chain",
    dependencies=[Depends(_check_enabled_and_auth)],
)
def run_trace_fixture(
    body: dict[str, Any],
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Execute a minimal tool call to produce a complete trace chain.

    Body:
        client_id: int
        fixture: one of cashflow | target_plan | termination
    """
    import uuid
    from app.utils.trace_context import set_current_trace_id
    from app.services.agent_trace_logger import log_trace_event

    client_id = body.get("client_id")
    fixture = body.get("fixture", "").strip().lower()

    if not client_id:
        raise HTTPException(status_code=422, detail="client_id is required")
    if fixture not in _VALID_FIXTURES:
        raise HTTPException(
            status_code=422,
            detail=f"fixture must be one of {sorted(_VALID_FIXTURES)}",
        )

    trace_id = f"fixture-{fixture}-{uuid.uuid4().hex[:8]}"
    set_current_trace_id(trace_id)

    # Log synthetic user_input
    log_trace_event(
        event_type="user_input",
        payload={
            "fixture": fixture,
            "client_id": client_id,
            "synthetic": True,
        },
        client_id=client_id,
        endpoint="/api/v1/debug/trace-fixtures/run",
    )

    notes: list[str] = []
    tool_result: str | None = None

    try:
        from app.services.llm_chat.tool_execution import execute_tool_call

        if fixture == "cashflow":
            tool_result = execute_tool_call(
                tool_name="RUN_RETIREMENT_CASHFLOW_ANALYSIS",
                args={"retirement_age": 67},
                client_id=int(client_id),
                db=db,
            )
            notes.append("Executed RUN_RETIREMENT_CASHFLOW_ANALYSIS with retirement_age=67")

        elif fixture == "target_plan":
            tool_result = execute_tool_call(
                tool_name="BUILD_TARGET_PENSION_PLAN",
                args={"target_monthly_pension": 15000},
                client_id=int(client_id),
                db=db,
            )
            notes.append("Executed BUILD_TARGET_PENSION_PLAN with target_monthly_pension=15000")

        elif fixture == "termination":
            tool_result = execute_tool_call(
                tool_name="PROCESS_TERMINATION",
                args={"confirmed": False},
                client_id=int(client_id),
                db=db,
                user_approved=False,
            )
            notes.append("Executed PROCESS_TERMINATION with confirmed=False (dry run / approval request)")

    except Exception as exc:
        notes.append(f"Tool execution raised: {type(exc).__name__}: {str(exc)[:500]}")

    # Log synthetic assistant_output
    log_trace_event(
        event_type="assistant_output",
        payload={
            "fixture": fixture,
            "result_preview": (tool_result or "")[:2000],
            "synthetic": True,
        },
        client_id=client_id,
        endpoint="/api/v1/debug/trace-fixtures/run",
    )

    return {
        "trace_id": trace_id,
        "fixture": fixture,
        "notes": notes,
    }
