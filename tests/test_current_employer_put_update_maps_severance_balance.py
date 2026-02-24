from datetime import date

from fastapi.testclient import TestClient

from app.main import app
from app.models.client import Client
from app.models.current_employment import CurrentEmployer


def test_put_update_current_employer_maps_severance_balance_to_accrued(
    db_session,
) -> None:
    client_id = 990000050

    client = db_session.query(Client).filter(Client.id == client_id).first()
    if client is None:
        client = Client(
            id=client_id,
            id_number_raw=str(client_id),
            id_number=str(client_id),
            full_name="PUT Mapping Test",
            birth_date=date(2000, 1, 1),
            gender="male",
            is_active=True,
            current_employer_exists=True,
        )
        db_session.add(client)
        db_session.flush()

    employer = CurrentEmployer(
        client_id=client.id,
        employer_name="Employer PUT",
        start_date=date(2020, 1, 1),
        end_date=None,
        last_salary=10000.0,
        severance_accrued=None,
        other_grants={},
    )
    db_session.add(employer)
    db_session.commit()

    api = TestClient(app)
    payload = {
        "severance_balance": 252695.89,
        "monthly_salary": 12345.0,
    }

    res = api.put(
        f"/api/v1/clients/{client_id}/current-employer/{employer.id}", json=payload
    )
    assert res.status_code == 200

    db_session.expire_all()
    refreshed = (
        db_session.query(CurrentEmployer)
        .filter(CurrentEmployer.id == employer.id)
        .first()
    )
    assert refreshed is not None

    assert abs(float(refreshed.severance_accrued or 0.0) - 252695.89) < 0.01
    assert abs(float(refreshed.last_salary or 0.0) - 12345.0) < 0.01
