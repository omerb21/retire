from datetime import datetime, timedelta, timezone


def test_trace_retention_cleanup_dry_run_and_delete(db_session, monkeypatch) -> None:
    from app.database import SessionLocal
    from app.models.agent_trace_event import AgentTraceEvent
    from app.services.agent_eyes import event_collector as ec

    ec._session_factory_override = SessionLocal

    db_session.query(AgentTraceEvent).delete(synchronize_session=False)
    db_session.commit()

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=30)

    tid_old = "stage17_retention_old"
    tid_border = "stage17_retention_border"
    tid_new = "stage17_retention_new"

    old = AgentTraceEvent(trace_id=tid_old, event_type="e", payload_json="{}", created_at=cutoff - timedelta(seconds=1))
    border = AgentTraceEvent(trace_id=tid_border, event_type="e", payload_json="{}", created_at=cutoff)
    new = AgentTraceEvent(trace_id=tid_new, event_type="e", payload_json="{}", created_at=cutoff + timedelta(seconds=1))

    db_session.add_all([old, border, new])
    db_session.commit()

    dry = ec.delete_trace_events_older_than(cutoff_dt=cutoff, dry_run=True)
    assert dry == 1

    remaining = (
        db_session.query(AgentTraceEvent)
        .filter(AgentTraceEvent.trace_id.in_([tid_old, tid_border, tid_new]))
        .count()
    )
    assert remaining == 3

    deleted = ec.delete_trace_events_older_than(cutoff_dt=cutoff, dry_run=False)
    assert deleted == 1

    remaining2 = (
        db_session.query(AgentTraceEvent)
        .filter(AgentTraceEvent.trace_id.in_([tid_old, tid_border, tid_new]))
        .order_by(AgentTraceEvent.created_at.asc())
        .all()
    )
    assert len(remaining2) == 2
    assert remaining2[0].trace_id == tid_border
    assert remaining2[1].trace_id == tid_new
