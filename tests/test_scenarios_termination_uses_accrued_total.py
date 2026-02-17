import logging

from datetime import date

from app.services.retirement import RetirementScenariosBuilder
from app.models.client import Client
from app.models.current_employment import CurrentEmployer, EmployerGrant, GrantType


def test_scenarios_termination_uses_accrued_total(db_session, caplog) -> None:
    caplog.set_level(logging.INFO)

    client_id = 990000020

    client = db_session.query(Client).filter(Client.id == client_id).first()
    if client is None:
        client = Client(
            id=client_id,
            id_number_raw=str(client_id),
            id_number=str(client_id),
            full_name="Scenario Termination Accrued Test",
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

    db_session.commit()

    builder = RetirementScenariosBuilder(
        db_session,
        client_id,
        retirement_age=67,
        pension_portfolio=None,
        use_current_employer_termination=True,
    )
    builder._build_max_pension_scenario()

    employer_latest = (
        db_session.query(CurrentEmployer)
        .filter(CurrentEmployer.client_id == client.id)
        .order_by(CurrentEmployer.id.desc())
        .first()
    )
    assert employer_latest is not None

    grants = (
        db_session.query(EmployerGrant)
        .filter(EmployerGrant.employer_id == int(employer_latest.id))
        .filter(EmployerGrant.grant_type == GrantType.severance)
        .all()
    )
    assert grants, "Expected at least one severance EmployerGrant"
    total = sum(float(g.grant_amount or 0) for g in grants)

    ssot_logs = [
        r.message
        for r in caplog.records
        if "SCENARIO_TERMINATION_SSOT" in str(r.message)
    ]
    assert ssot_logs, "Expected SCENARIO_TERMINATION_SSOT log line"

    print(ssot_logs[-1])

    assert abs(total - 252695.0) < 0.01, (
        f"grant_total={total} expected=252695.0 employer_id={employer_latest.id} "
        f"SSOT={ssot_logs[-1]}"
    )
