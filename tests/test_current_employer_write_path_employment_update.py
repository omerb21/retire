import logging
import re
from datetime import date

from app.models.client import Client
from app.models.current_employment import CurrentEmployer
from app.schemas.current_employer import CurrentEmployerCreate
from app.services.current_employer.employment import EmploymentService


def test_current_employer_write_path_persists_severance_accrued_after(
    db_session, caplog
) -> None:
    caplog.set_level(logging.INFO)

    client_id = 990000030

    client = db_session.query(Client).filter(Client.id == client_id).first()
    if client is None:
        client = Client(
            id=client_id,
            id_number_raw=str(client_id),
            id_number=str(client_id),
            full_name="CurrentEmployer WritePath Test",
            birth_date=date(2000, 1, 1),
            gender="male",
            is_active=True,
            current_employer_exists=True,
        )
        db_session.add(client)
        db_session.flush()

    employer = CurrentEmployer(
        client_id=client.id,
        employer_name="Employer A",
        start_date=date(2020, 1, 1),
        last_salary=10000.0,
        severance_accrued=555.0,
        other_grants={},
    )
    db_session.add(employer)
    db_session.commit()

    service = EmploymentService(db_session)
    payload_sev = 12345.0

    employer_data = CurrentEmployerCreate(
        employer_name="Employer A",
        start_date=date(2020, 1, 1),
        monthly_salary=10000.0,
        severance_balance=payload_sev,
    )

    service.create_or_update_employer(client_id=client.id, employer_data=employer_data)

    log_lines = [
        r.message
        for r in caplog.records
        if "CURRENT_EMPLOYER_WRITE_PATH" in str(r.message)
    ]
    assert log_lines, "Expected CURRENT_EMPLOYER_WRITE_PATH log line"

    m = re.search(r"severance_accrued_after=([^\s]+)", str(log_lines[-1]))
    assert (
        m is not None
    ), f"Could not parse severance_accrued_after from log: {log_lines[-1]}"

    after_raw = m.group(1)
    after_value = float(after_raw)
    assert after_value != 0.0

    employer_latest = (
        db_session.query(CurrentEmployer)
        .filter(CurrentEmployer.client_id == client.id)
        .order_by(CurrentEmployer.updated_at.desc(), CurrentEmployer.id.desc())
        .first()
    )
    assert employer_latest is not None

    assert float(employer_latest.severance_accrued or 0.0) == after_value
    assert abs(after_value - payload_sev) < 0.01
