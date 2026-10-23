"""Regression coverage for snapshot restore termination foreign keys."""

from app.models.current_employment import CurrentEmployer
from app.models.pension_fund import PensionFund
from app.services.snapshot_service import SnapshotService


def test_synthetic_current_employer_termination_does_not_create_invalid_employment_fk(
    db_session, client
):
    client_id = int(client.id)
    employer = CurrentEmployer(
        client_id=client_id,
        employer_name="Test Employer",
        start_date=__import__("datetime").date(2022, 1, 1),
        other_grants={
            "termination_confirmed": True,
            "termination_date": "2030-11-02",
        },
    )
    db_session.add(employer)
    db_session.commit()

    service = SnapshotService(db_session)
    saved = service.save_snapshot(client_id)
    marker = saved["snapshot"]["data"]["termination_event"]
    assert marker is not None
    assert marker.get("employment_id") is None

    restored = service.restore_snapshot(client_id, saved)
    assert restored["success"] is True

    from app.models.termination_event import TerminationEvent
    assert (
        db_session.query(TerminationEvent)
        .filter(TerminationEvent.client_id == client_id)
        .count()
        == 0
    )
    restored_employer = (
        db_session.query(CurrentEmployer)
        .filter(CurrentEmployer.client_id == client_id)
        .first()
    )
    assert restored_employer is not None
    assert restored_employer.other_grants.get("termination_confirmed") is True


def test_real_termination_snapshot_preserves_employment_id(db_session):
    from app.models.termination_event import TerminationEvent
    from datetime import date
    event = TerminationEvent(
        client_id=1,
        employment_id=123,
        actual_termination_date=date(2030, 11, 2),
    )
    serialized = SnapshotService(db_session)._serialize_termination_event(event)
    assert serialized["employment_id"] == 123
