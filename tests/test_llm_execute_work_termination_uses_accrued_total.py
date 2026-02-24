import json
from datetime import date

import app.services.llm_chat.tool_execution as tool_execution
from app.models.client import Client
from app.models.current_employment.employer import CurrentEmployer
from app.services.current_employer import TerminationService


def test_execute_work_termination_uses_accrued_total_when_greater(db_session) -> None:
    client_id = 990000010

    client = db_session.query(Client).filter(Client.id == client_id).first()
    if client is None:
        client = Client(
            id=client_id,
            id_number_raw=str(client_id),
            id_number=str(client_id),
            full_name="Execute Work Termination Accrued Test",
            birth_date=date(1980, 1, 1),
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
            employer_name="Accrued Employer",
            start_date=date(2024, 1, 1),
            end_date=None,
            last_salary=10000.0,
            severance_accrued=252695.0,
            other_grants={"termination_date": "2025-01-01"},
            continuity_years=0.0,
        )
        db_session.add(employer)
        db_session.flush()
    else:
        employer.start_date = date(2024, 1, 1)
        employer.end_date = None
        employer.last_salary = 10000.0
        employer.severance_accrued = 252695.0
        employer.other_grants = {"termination_date": "2025-01-01"}
        employer.continuity_years = 0.0
        db_session.add(employer)
        db_session.flush()

    db_session.commit()

    svc = TerminationService(db_session)
    calc = svc.calculate_severance(
        start_date=employer.start_date,
        end_date=date(2025, 1, 1),
        last_salary=float(employer.last_salary or 0),
        continuity_years=float(getattr(employer, "continuity_years", 0.0) or 0.0),
    )
    formula_total = float(calc.get("severance_amount") or 0)

    out = tool_execution.execute_tool_call(
        tool_name="EXECUTE_WORK_TERMINATION",
        args={
            "termination_date": "2025-01-01",
            "termination_reason": "layoff",
            "calculate_severance": True,
        },
        client_id=int(client.id),
        db=db_session,
        pension_portfolio=None,
        user_approved=True,
    )

    parsed = json.loads(out)
    sev = parsed.get("severance_calculated") or {}

    severance_amount = float(sev.get("severance_amount") or 0)

    assert severance_amount >= formula_total
    assert abs(severance_amount - 252695.0) < 0.01
