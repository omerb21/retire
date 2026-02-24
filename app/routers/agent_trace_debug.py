"""
Debug API for Agent Eyes trace inspection.

Security:
  - Active only when AGENT_TRACE_DEBUG_ENABLED=1
  - Requires header X-Admin-Token matching env ADMIN_DEBUG_TOKEN
  - Returns 404 when disabled, 401 on bad/missing token
"""

import json
import os
import ipaddress
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import Response
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.agent_trace_event import AgentTraceEvent

router = APIRouter(prefix="/api/v1/debug", tags=["agent-trace-debug"])


def _hex_preview(data: bytes, max_len: int = 96) -> str:
    try:
        chunk = data[: max(0, int(max_len))]
    except Exception:
        chunk = data
    try:
        return " ".join(f"{b:02x}" for b in chunk)
    except Exception:
        return ""


def _json_utf8_response(payload: Any) -> Response:
    return Response(
        content=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        media_type="application/json; charset=utf-8",
    )


def _check_enabled_and_auth(
    request: Request,
    x_admin_token: Optional[str] = Header(None),
) -> None:
    """Dependency: verify feature flag + admin token."""
    enabled = (os.getenv("AGENT_TRACE_DEBUG_ENABLED") or "").strip()
    if enabled != "1":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    expected_token = (os.getenv("ADMIN_DEBUG_TOKEN") or "").strip()
    if expected_token:
        if not x_admin_token or x_admin_token.strip() != expected_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin token"
            )
        return

    app_env = (os.getenv("APP_ENV") or "").strip().lower()
    is_dev = app_env == "development"

    host = None
    try:
        host = request.client.host if request.client else None
    except Exception:
        host = None

    is_loopback = False
    if host:
        if host == "localhost":
            is_loopback = True
        else:
            try:
                is_loopback = bool(ipaddress.ip_address(host).is_loopback)
            except Exception:
                is_loopback = False

    if is_dev and is_loopback:
        return

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin token not configured"
    )


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
        results.append(
            {
                "trace_id": row.trace_id,
                "first_event": row.first_event.isoformat() if row.first_event else None,
                "last_event": row.last_event.isoformat() if row.last_event else None,
                "event_count": row.event_count,
            }
        )
    return results


@router.get(
    "/traces/{trace_id}",
    summary="Get all events for a trace",
    dependencies=[Depends(_check_enabled_and_auth)],
)
def get_trace_events(
    trace_id: str,
    db: Session = Depends(get_db),
) -> Response:
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
    return _json_utf8_response([_row_to_dict(e) for e in events])


@router.get(
    "/traces/{trace_id}/events/{event_id}/payload-raw",
    summary="Get raw payload_json bytes for one trace event",
    dependencies=[Depends(_check_enabled_and_auth)],
)
def get_trace_event_payload_raw(
    trace_id: str,
    event_id: int,
    db: Session = Depends(get_db),
) -> Response:
    row = (
        db.query(AgentTraceEvent)
        .filter(AgentTraceEvent.trace_id == trace_id)
        .filter(AgentTraceEvent.id == event_id)
        .first()
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
        )

    payload = row.payload_json or ""
    raw = payload.encode("utf-8", errors="replace")
    return Response(content=raw, media_type="application/json")


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
) -> Response:
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
    evidence: dict[str, Any] = {}

    try:
        from app.services.llm_agent_tools_service import AgentToolsService
        from app.services.llm_chat.orchestration_utils_parts.blocked_balances_policy import (
            build_default_termination_plan_preview,
            store_current_employer_termination_plan_preview,
        )

        def _log_tool_call(tool_name: str, args: dict) -> str | None:
            tool_call_id = None
            try:
                tool_call_id = uuid.uuid4().hex
            except Exception:
                tool_call_id = None

            evidence.setdefault("tool_calls", []).append(
                {"tool_name": tool_name, "tool_call_id": tool_call_id}
            )
            log_trace_event(
                event_type="tool_call",
                payload={
                    "tool_name": tool_name,
                    "tool_call_id": tool_call_id,
                    "args": args,
                    "synthetic": True,
                },
                client_id=client_id,
                endpoint="/api/v1/debug/trace-fixtures/run",
            )

            return tool_call_id

        def _log_tool_result(
            tool_name: str,
            result: str,
            tool_call_id: str | None,
            success: bool = True,
        ) -> None:
            preview = (result or "")[:2000]
            preview_bytes = preview.encode("utf-8", errors="replace")

            evidence["tool_result_pre_write"] = {
                "tool_name": tool_name,
                "tool_call_id": tool_call_id,
                "status": "ok" if bool(success) else "error_safe",
                "success": bool(success),
                "result_preview": preview,
                "result_preview_utf8_hex": _hex_preview(preview_bytes),
            }

            log_trace_event(
                event_type="tool_result",
                payload={
                    "tool_name": tool_name,
                    "tool_call_id": tool_call_id,
                    "status": "ok" if bool(success) else "error_safe",
                    "success": bool(success),
                    "result_preview": preview,
                    "result_length": len(result or ""),
                    "synthetic": True,
                },
                client_id=client_id,
                endpoint="/api/v1/debug/trace-fixtures/run",
            )

            try:
                stored = (
                    db.query(AgentTraceEvent)
                    .filter(AgentTraceEvent.trace_id == trace_id)
                    .filter(AgentTraceEvent.event_type == "tool_result")
                    .order_by(
                        AgentTraceEvent.created_at.desc(), AgentTraceEvent.id.desc()
                    )
                    .first()
                )
                if stored is not None and stored.payload_json:
                    stored_bytes = stored.payload_json.encode("utf-8", errors="replace")
                    stored_preview = None
                    try:
                        parsed = json.loads(stored.payload_json)
                        if isinstance(parsed, dict):
                            stored_preview = parsed.get("result_preview")
                    except Exception:
                        stored_preview = None
                    stored_preview_bytes = (
                        (stored_preview or "").encode("utf-8", errors="replace")
                        if isinstance(stored_preview, str)
                        else b""
                    )
                    evidence["tool_result_from_db"] = {
                        "event_id": stored.id,
                        "tool_name": tool_name,
                        "tool_call_id": tool_call_id,
                        "payload_json_utf8_hex": _hex_preview(stored_bytes),
                        "result_preview": stored_preview,
                        "result_preview_utf8_hex": _hex_preview(stored_preview_bytes),
                    }
            except Exception:
                pass

        if fixture == "cashflow":
            tool_name = "RUN_RETIREMENT_CASHFLOW_ANALYSIS"
            args = {"age": 67}
            tool_call_id = _log_tool_call(tool_name, args)
            agent_tools = AgentToolsService(db=db, client_id=int(client_id))
            res = agent_tools.run_retirement_cashflow_analysis(
                retirement_date="",
                desired_monthly_income=None,
                apply_max_exemption=False,
                desired_income_is_net=None,
                explicit_age=67,
                explicit_gender=None,
            )
            tool_result = json.dumps(res, ensure_ascii=False)
            _log_tool_result(
                tool_name,
                tool_result,
                tool_call_id,
                success=bool(isinstance(res, dict) and res.get("success")),
            )
            notes.append(
                "Executed RUN_RETIREMENT_CASHFLOW_ANALYSIS via AgentToolsService"
            )

        elif fixture == "target_plan":
            tool_name = "BUILD_TARGET_PENSION_PLAN"
            args = {"target_monthly_pension": 15000}
            tool_call_id = _log_tool_call(tool_name, args)
            agent_tools = AgentToolsService(db=db, client_id=int(client_id))
            res = agent_tools.build_target_pension_plan(target_monthly_pension=15000.0)
            tool_result = json.dumps(res, ensure_ascii=False)
            _log_tool_result(
                tool_name,
                tool_result,
                tool_call_id,
                success=bool(isinstance(res, dict) and res.get("success")),
            )
            notes.append("Executed BUILD_TARGET_PENSION_PLAN via AgentToolsService")

        elif fixture == "termination":
            tool_name = "PROCESS_TERMINATION"
            args = {"confirmed": False}
            tool_call_id = _log_tool_call(tool_name, args)

            preview_text, default_template = build_default_termination_plan_preview(
                current_employer_amount=0.0,
                context=None,
            )
            try:
                store_current_employer_termination_plan_preview(
                    db=db,
                    client_id=int(client_id),
                    payload={
                        "plan_args": {},
                        "termination_arguments_template": dict(default_template),
                        "awaiting_user_confirmation": True,
                        "approved": False,
                        "declined": False,
                    },
                )
            except Exception:
                pass

            tool_result = preview_text
            _log_tool_result(tool_name, tool_result, tool_call_id, success=True)
            notes.append(
                "Generated PROCESS_TERMINATION preview via blocked_balances_policy"
            )

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

    return _json_utf8_response(
        {
            "trace_id": trace_id,
            "fixture": fixture,
            "notes": notes,
            "evidence": evidence,
        }
    )
