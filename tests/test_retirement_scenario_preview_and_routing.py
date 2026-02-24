import json

from datetime import date

import logging

from fastapi.testclient import TestClient

from app.main import app
from app.models.client import Client
from app.models.current_employment import CurrentEmployer
from app.models.current_employment import EmployerGrant
from app.models.pension_fund import PensionFund
from app.models.scenario import Scenario


def _ensure_client_employer_and_scenario(
    *, db_session, client_id: int, scenario_id: int
) -> int:
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
            start_date=date(2020, 1, 1),
            end_date=date(2025, 12, 31),
            last_salary=10000.0,
            severance_accrued=252695.0,
            continuity_years=0.0,
            other_grants={},
        )
        db_session.add(employer)
        db_session.flush()
    else:
        employer.employer_name = "Scenario Employer"
        employer.start_date = date(2020, 1, 1)
        employer.end_date = date(2025, 12, 31)
        employer.last_salary = 10000.0
        employer.severance_accrued = 252695.0
        employer.continuity_years = 0.0
        employer.other_grants = {}
        db_session.add(employer)
        db_session.flush()

    scenario = db_session.query(Scenario).filter(Scenario.id == scenario_id).first()

    if scenario is None or int(getattr(scenario, "client_id", 0) or 0) != int(
        client.id
    ):
        scenario = Scenario(
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
        db_session.flush()
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

    return int(scenario.id)


def test_retirement_scenario_preview_does_not_modify_current_employer(
    db_session,
) -> None:
    client_id = 990000040
    scenario_id = 66

    scenario_id = _ensure_client_employer_and_scenario(
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

    res = api.get(
        f"/api/v1/clients/{client_id}/retirement-scenarios/{scenario_id}/preview"
    )
    assert res.status_code == 200, res.text

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

    scenario_id = _ensure_client_employer_and_scenario(
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

    res = api.post(
        f"/api/v1/clients/{client_id}/retirement-scenarios/{scenario_id}/execute"
    )
    assert res.status_code == 200, res.text
    payload = res.json()
    assert payload.get("success") is True
    assert int(payload.get("actions_count") or 0) > 0

    db_session.expire_all()
    employer_latest = (
        db_session.query(CurrentEmployer)
        .filter(CurrentEmployer.client_id == client_id)
        .order_by(CurrentEmployer.id.desc())
        .first()
    )
    assert employer_latest is not None

    assert employer_latest.end_date == end_date_before
    assert float(employer_latest.severance_accrued or 0.0) == sev_before

    grants_after = (
        db_session.query(EmployerGrant)
        .join(CurrentEmployer, EmployerGrant.employer_id == CurrentEmployer.id)
        .filter(CurrentEmployer.client_id == client_id)
        .all()
    )

    assert grants_after
    grant_sum = sum(float(getattr(g, "grant_amount", 0.0) or 0.0) for g in grants_after)
    assert abs(grant_sum - sev_before) < 0.1


def test_retirement_scenario_execute_logs_sources_and_skips_reset(
    db_session, caplog
) -> None:
    caplog.set_level(logging.INFO)

    client_id = 990000043
    scenario_id = 68

    scenario_id = _ensure_client_employer_and_scenario(
        db_session=db_session,
        client_id=client_id,
        scenario_id=scenario_id,
    )

    api = TestClient(app)
    res = api.post(
        f"/api/v1/clients/{client_id}/retirement-scenarios/{scenario_id}/execute"
    )
    assert res.status_code == 200, res.text

    lines = [str(r.message) for r in caplog.records]

    term_date_line = next(
        (l for l in lines if "SCENARIO_TERMINATION_DATE_SOURCE" in l), None
    )
    assert term_date_line is not None
    assert "source=employer_end_date" in term_date_line
    print(term_date_line)

    sev_source_line = next(
        (l for l in lines if "SCENARIO_SEVERANCE_AMOUNT_SOURCE" in l), None
    )
    assert sev_source_line is not None
    assert "severance_source=employer_severance_accrued" in sev_source_line
    print(sev_source_line)

    reset_line = next((l for l in lines if "TERMINATION_SEVERANCE_RESET" in l), None)
    assert reset_line is not None
    assert "reset=false" in reset_line
    print(reset_line)


def test_retirement_scenario_uses_complete_current_employer_when_multiple_exist(
    db_session, caplog
) -> None:
    caplog.set_level(logging.INFO)

    client_id = 990000044
    scenario_id = 69

    scenario_id = _ensure_client_employer_and_scenario(
        db_session=db_session,
        client_id=client_id,
        scenario_id=scenario_id,
    )

    db_session.expire_all()
    employer_complete = (
        db_session.query(CurrentEmployer)
        .filter(CurrentEmployer.client_id == client_id)
        .order_by(CurrentEmployer.id.desc())
        .first()
    )
    assert employer_complete is not None

    sev_complete = float(employer_complete.severance_accrued or 0.0)
    assert sev_complete > 0.0

    employer_placeholder = CurrentEmployer(
        client_id=client_id,
        employer_name="Scenario Employer (placeholder)",
        start_date=getattr(employer_complete, "start_date", date(2020, 1, 1)),
        end_date=getattr(employer_complete, "end_date", None),
        last_salary=None,
        severance_accrued=None,
        continuity_years=0.0,
        other_grants={},
    )
    db_session.add(employer_placeholder)
    db_session.commit()

    api = TestClient(app)
    preview = api.get(
        f"/api/v1/clients/{client_id}/retirement-scenarios/{scenario_id}/preview"
    )
    assert preview.status_code == 200, preview.text

    execute = api.post(
        f"/api/v1/clients/{client_id}/retirement-scenarios/{scenario_id}/execute"
    )
    assert execute.status_code == 200, execute.text

    db_session.expire_all()
    chosen_employer = (
        db_session.query(CurrentEmployer)
        .filter(CurrentEmployer.client_id == client_id)
        .order_by(CurrentEmployer.updated_at.desc(), CurrentEmployer.id.desc())
        .first()
    )
    assert chosen_employer is not None

    grants_after = (
        db_session.query(EmployerGrant)
        .join(CurrentEmployer, EmployerGrant.employer_id == CurrentEmployer.id)
        .filter(CurrentEmployer.client_id == client_id)
        .all()
    )
    assert grants_after
    grant_sum = sum(float(getattr(g, "grant_amount", 0.0) or 0.0) for g in grants_after)
    assert abs(grant_sum - sev_complete) < 0.1

    lines = [str(r.message) for r in caplog.records]
    selected_line = next(
        (
            l
            for l in lines
            if "CURRENT_EMPLOYER_SELECTED" in l and f"client_id={client_id}" in l
        ),
        None,
    )
    assert selected_line is not None
    assert "reason=fallback_complete_due_to_missing_latest_fields" in selected_line


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
