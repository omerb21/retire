import json

from datetime import date

from fastapi.testclient import TestClient

from app.main import app
from app.models.client import Client
from app.models.current_employment import CurrentEmployer
from app.models.current_employment import EmployerGrant
from app.models.pension_fund import PensionFund
from app.models.scenario import Scenario


def _ensure_client_employer_and_scenario(*, db_session, client_id: int, scenario_id: int) -> None:
    client = db_session.query(Client).filter(Client.id == client_id).first()
    if client is None:
        client = Client(
            id=client_id,
            id_number_raw=str(client_id),
            id_number=str(client_id),
            full_name="Preview Scenario Test",
            birth_date=date(2000, 1, 1),
            gender="male",
            is_active=True,
            current_employer_exists=True,
        )
        db_session.add(client)
        db_session.flush()

    employer = (
        db_session.query(CurrentEmployer)
        .filter(CurrentEmployer.client_id == client.id)
        .order_by(CurrentEmployer.id.desc())
        .first()
    )
    if employer is None:
        employer = CurrentEmployer(
            client_id=client.id,
            employer_name="Scenario Employer",
            start_date=date(2066, 1, 1),
            end_date=None,
            last_salary=10000.0,
            severance_accrued=252695.0,
            continuity_years=0.0,
            other_grants={},
        )
        db_session.add(employer)
        db_session.flush()
    else:
        employer.employer_name = "Scenario Employer"
        employer.start_date = date(2066, 1, 1)
        employer.end_date = None
        employer.last_salary = 10000.0
        employer.severance_accrued = 252695.0
        employer.continuity_years = 0.0
        employer.other_grants = {}
        db_session.add(employer)
        db_session.flush()

    scenario = db_session.query(Scenario).filter(Scenario.id == scenario_id).first()
    if scenario is None:
        scenario = Scenario(
            id=scenario_id,
            client_id=client.id,
            scenario_name="Scenario 1",
            parameters=json.dumps(
                {
                    "retirement_age": 67,
                    "scenario_type": "scenario_1_max_pension",
                    "pension_portfolio": None,
                    "include_current_employer_termination": True,
                }
            ),
            summary_results=None,
            cashflow_projection=None,
        )
        db_session.add(scenario)
    else:
        scenario.parameters = json.dumps(
            {
                "retirement_age": 67,
                "scenario_type": "scenario_1_max_pension",
                "pension_portfolio": None,
                "include_current_employer_termination": True,
            }
        )
        db_session.add(scenario)

    db_session.commit()


def test_retirement_scenario_preview_does_not_modify_current_employer(db_session) -> None:
    client_id = 990000040
    scenario_id = 66

    _ensure_client_employer_and_scenario(
        db_session=db_session,
        client_id=client_id,
        scenario_id=scenario_id,
    )

    api = TestClient(app)

    employer_before = (
        db_session.query(CurrentEmployer)
        .filter(CurrentEmployer.client_id == client_id)
        .order_by(CurrentEmployer.id.desc())
        .first()
    )
    assert employer_before is not None
    end_date_before = employer_before.end_date
    sev_before = float(employer_before.severance_accrued or 0.0)
    grants_before = (
        db_session.query(EmployerGrant)
        .join(CurrentEmployer, EmployerGrant.employer_id == CurrentEmployer.id)
        .filter(CurrentEmployer.client_id == client_id)
        .count()
    )
    pension_funds_before = (
        db_session.query(PensionFund).filter(PensionFund.client_id == client_id).count()
    )

    res = api.get(f"/api/v1/clients/{client_id}/retirement-scenarios/{scenario_id}/preview")
    assert res.status_code == 200

    db_session.expire_all()
    employer_latest = (
        db_session.query(CurrentEmployer)
        .filter(CurrentEmployer.client_id == client_id)
        .order_by(CurrentEmployer.id.desc())
        .first()
    )
    assert employer_latest is not None
    assert float(employer_latest.severance_accrued or 0.0) == sev_before
    assert employer_latest.end_date == end_date_before

    grants_after = (
        db_session.query(EmployerGrant)
        .join(CurrentEmployer, EmployerGrant.employer_id == CurrentEmployer.id)
        .filter(CurrentEmployer.client_id == client_id)
        .count()
    )
    pension_funds_after = (
        db_session.query(PensionFund).filter(PensionFund.client_id == client_id).count()
    )
    assert grants_after == grants_before
    assert pension_funds_after == pension_funds_before


def test_retirement_scenario_execute_modifies_current_employer(db_session) -> None:
    client_id = 990000041
    scenario_id = 67

    _ensure_client_employer_and_scenario(
        db_session=db_session,
        client_id=client_id,
        scenario_id=scenario_id,
    )

    api = TestClient(app)
    res = api.post(f"/api/v1/clients/{client_id}/retirement-scenarios/{scenario_id}/execute")
    assert res.status_code == 200

    db_session.expire_all()
    employer_latest = (
        db_session.query(CurrentEmployer)
        .filter(CurrentEmployer.client_id == client_id)
        .order_by(CurrentEmployer.id.desc())
        .first()
    )
    assert employer_latest is not None
    assert float(employer_latest.severance_accrued or 0.0) != 252695.0


def test_current_employer_grants_route_not_swallowed_by_employer_id(db_session) -> None:
    client_id = 990000042

    client = db_session.query(Client).filter(Client.id == client_id).first()
    if client is None:
        client = Client(
            id=client_id,
            id_number_raw=str(client_id),
            id_number=str(client_id),
            full_name="Routing Test",
            birth_date=date(2000, 1, 1),
            gender="male",
            is_active=True,
            current_employer_exists=True,
        )
        db_session.add(client)
        db_session.commit()

    api = TestClient(app)
    res = api.get(f"/api/v1/clients/{client_id}/current-employer/grants")

    assert res.status_code != 422
