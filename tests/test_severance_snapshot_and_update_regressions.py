from datetime import date

from app.models.client import Client
from app.models.current_employment import CurrentEmployer
from app.schemas.current_employer import CurrentEmployerUpdate
from app.services.current_employer_service import CurrentEmployerService
from app.services.snapshot_service import SnapshotService


def test_snapshot_roundtrip_does_not_reset_severance_accrued(db_session) -> None:
    client_id = 992000001

    client = db_session.query(Client).filter(Client.id == client_id).first()
    if client is None:
        client = Client(
            id=client_id,
            id_number_raw=str(client_id),
            id_number=str(client_id),
            full_name="Snapshot Roundtrip",
            birth_date=date(1980, 1, 1),
            gender="male",
            is_active=True,
            current_employer_exists=True,
        )
        db_session.add(client)
        db_session.flush()

    employer = CurrentEmployer(
        client_id=client_id,
        employer_name="Emp",
        start_date=date(2020, 1, 1),
        last_salary=10000.0,
        severance_accrued=252000.0,
        other_grants={},
    )
    db_session.add(employer)
    db_session.commit()

    service = SnapshotService(db_session)
    snap = service.save_snapshot(client_id, "t")
    assert snap.get("success") is True

    restored = service.restore_snapshot(client_id, snap)
    assert restored.get("success") is True

    db_session.expire_all()
    employer_after = (
        db_session.query(CurrentEmployer)
        .filter(CurrentEmployer.client_id == client_id)
        .order_by(CurrentEmployer.updated_at.desc(), CurrentEmployer.id.desc())
        .first()
    )
    assert employer_after is not None
    assert abs(float(employer_after.severance_accrued or 0.0) - 252000.0) < 0.01


def test_update_current_employer_does_not_clear_severance_when_field_missing(db_session) -> None:
    client_id = 992000002

    client = db_session.query(Client).filter(Client.id == client_id).first()
    if client is None:
        client = Client(
            id=client_id,
            id_number_raw=str(client_id),
            id_number=str(client_id),
            full_name="Update Preserve",
            birth_date=date(1980, 1, 1),
            gender="male",
            is_active=True,
            current_employer_exists=True,
        )
        db_session.add(client)
        db_session.flush()

    employer = CurrentEmployer(
        client_id=client_id,
        employer_name="Emp",
        start_date=date(2020, 1, 1),
        last_salary=10000.0,
        severance_accrued=252000.0,
        other_grants={},
    )
    db_session.add(employer)
    db_session.commit()

    update = CurrentEmployerUpdate(employer_name="Emp Updated")
    updated = CurrentEmployerService.update_current_employer_for_client(
        db=db_session,
        client_id=client_id,
        employer_id=employer.id,
        employer_data=update,
    )
    assert updated is not None

    db_session.expire_all()
    after = db_session.query(CurrentEmployer).filter(CurrentEmployer.id == employer.id).first()
    assert after is not None
    assert abs(float(after.severance_accrued or 0.0) - 252000.0) < 0.01
