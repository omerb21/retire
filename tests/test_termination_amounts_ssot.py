import json
from datetime import date

import app.services.llm_chat.tool_execution as tool_execution
from app.models.client import Client
from app.models.current_employment.employer import CurrentEmployer
from app.services.current_employer import TerminationService
from app.services.llm_chat.orchestration_utils_parts.blocked_balances_policy import (
    store_current_employer_termination_plan_preview,
)


def _setup_client_and_employer(db_session, *, client_id: int, start_date: date, end_date: date, last_salary: float, severance_accrued: float) -> tuple[int, int]:
    client = db_session.query(Client).filter(Client.id == client_id).first()
    if client is None:
        client = Client(
            id=client_id,
            id_number_raw=str(client_id),
            id_number=str(client_id),
            full_name="SSOT Termination Test",
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
            employer_name="SSOT Employer",
            start_date=start_date,
            end_date=end_date,
            last_salary=last_salary,
            severance_accrued=severance_accrued,
        )
        db_session.add(employer)
        db_session.flush()
    else:
        employer.start_date = start_date
        employer.end_date = end_date
        employer.last_salary = last_salary
        employer.severance_accrued = severance_accrued
        db_session.add(employer)
        db_session.flush()

    db_session.commit()
    return int(client.id), int(employer.id)


def _compute_formula_and_exempt(db_session, *, start_date: date, end_date: date, last_salary: float) -> tuple[float, float]:
    svc = TerminationService(db_session)
    calc = svc.calculate_severance(
        start_date=start_date,
        end_date=end_date,
        last_salary=float(last_salary),
        continuity_years=0.0,
    )
    formula_total = float(calc.get("severance_amount") or 0)
    exempt_amount = float(calc.get("exempt_amount") or 0)
    return formula_total, exempt_amount


def _extract_tool_json(result: str) -> dict:
    assert isinstance(result, str)
    return json.loads(result.split("###SEVERANCE_RESET###", 1)[0])


def _approve_default_termination_preview(db_session, *, client_id: int, termination_date: date) -> None:
    store_current_employer_termination_plan_preview(
        db=db_session,
        client_id=int(client_id),
        payload={
            "termination_arguments_template": {
                "confirmed": True,
                "termination_date": termination_date.isoformat(),
                "exempt_choice": "redeem_with_exemption",
                "taxable_choice": "annuity",
            },
            "awaiting_user_confirmation": False,
            "approved": True,
            "declined": False,
            "used": False,
        },
    )


def test_ssot_accrued_greater_than_formula(db_session, client) -> None:
    start = date(2020, 1, 1)
    end = date(2025, 1, 1)

    last_salary = 10000.0
    formula_total, exempt_amount_expected = _compute_formula_and_exempt(
        db_session, start_date=start, end_date=end, last_salary=last_salary
    )

    accrued_total = float(formula_total) + 12345.0
    client_id, _ = _setup_client_and_employer(
        db_session,
        client_id=930000001,
        start_date=start,
        end_date=end,
        last_salary=last_salary,
        severance_accrued=accrued_total,
    )

    out_exec = tool_execution.execute_tool_call(
        tool_name="EXECUTE_WORK_TERMINATION",
        args={
            "termination_date": end.isoformat(),
            "termination_reason": "layoff",
            "final_salary": last_salary,
            "calculate_severance": True,
        },
        client_id=client_id,
        db=db_session,
        pension_portfolio=None,
        user_approved=True,
    )
    payload_exec = _extract_tool_json(out_exec)
    sev_exec = (payload_exec.get("severance_calculated") or {})
    assert abs(float(sev_exec.get("severance_amount") or 0) - float(accrued_total)) < 0.01
    assert abs(float(sev_exec.get("exempt_amount") or 0) - float(exempt_amount_expected)) < 0.01

    _approve_default_termination_preview(db_session, client_id=client_id, termination_date=end)
    out_proc = tool_execution.execute_tool_call(
        tool_name="PROCESS_TERMINATION",
        args={
            "termination_date": end.isoformat(),
            "exempt_choice": "redeem_with_exemption",
            "taxable_choice": "annuity",
            "confirmed": True,
        },
        client_id=client_id,
        db=db_session,
        pension_portfolio=[],
        user_approved=True,
    )
    payload_proc = _extract_tool_json(out_proc)
    details = (payload_proc.get("details") or {})

    assert abs(float(details.get("severance_amount") or 0) - float(accrued_total)) < 0.01
    assert abs(float(details.get("exempt_amount") or 0) - float(exempt_amount_expected)) < 0.01

    expected_taxable = max(0.0, float(accrued_total) - float(exempt_amount_expected))
    assert abs(float(details.get("taxable_amount") or 0) - float(expected_taxable)) < 0.01


def test_ssot_accrued_lower_than_formula(db_session, client) -> None:
    start = date(2020, 1, 1)
    end = date(2025, 1, 1)

    last_salary = 10000.0
    formula_total, exempt_amount_expected = _compute_formula_and_exempt(
        db_session, start_date=start, end_date=end, last_salary=last_salary
    )

    accrued_total = max(0.0, float(formula_total) - 2222.0)
    client_id, _ = _setup_client_and_employer(
        db_session,
        client_id=930000002,
        start_date=start,
        end_date=end,
        last_salary=last_salary,
        severance_accrued=accrued_total,
    )

    out_exec = tool_execution.execute_tool_call(
        tool_name="EXECUTE_WORK_TERMINATION",
        args={
            "termination_date": end.isoformat(),
            "termination_reason": "layoff",
            "final_salary": last_salary,
            "calculate_severance": True,
        },
        client_id=client_id,
        db=db_session,
        pension_portfolio=None,
        user_approved=True,
    )
    payload_exec = _extract_tool_json(out_exec)
    sev_exec = (payload_exec.get("severance_calculated") or {})
    assert abs(float(sev_exec.get("severance_amount") or 0) - float(formula_total)) < 0.01
    assert abs(float(sev_exec.get("exempt_amount") or 0) - float(exempt_amount_expected)) < 0.01

    _approve_default_termination_preview(db_session, client_id=client_id, termination_date=end)
    out_proc = tool_execution.execute_tool_call(
        tool_name="PROCESS_TERMINATION",
        args={
            "termination_date": end.isoformat(),
            "exempt_choice": "redeem_with_exemption",
            "taxable_choice": "annuity",
            "confirmed": True,
        },
        client_id=client_id,
        db=db_session,
        pension_portfolio=[],
        user_approved=True,
    )
    payload_proc = _extract_tool_json(out_proc)
    details = (payload_proc.get("details") or {})

    assert abs(float(details.get("severance_amount") or 0) - float(formula_total)) < 0.01
    assert abs(float(details.get("exempt_amount") or 0) - float(exempt_amount_expected)) < 0.01

    expected_taxable = max(0.0, float(formula_total) - float(exempt_amount_expected))
    assert abs(float(details.get("taxable_amount") or 0) - float(expected_taxable)) < 0.01


def test_ssot_consistency_between_both_paths(db_session, client) -> None:
    start = date(2020, 1, 1)
    end = date(2025, 1, 1)

    last_salary = 10000.0
    formula_total, _exempt_amount_expected = _compute_formula_and_exempt(
        db_session, start_date=start, end_date=end, last_salary=last_salary
    )

    accrued_total = float(formula_total) + 9999.0
    client_id, _ = _setup_client_and_employer(
        db_session,
        client_id=930000003,
        start_date=start,
        end_date=end,
        last_salary=last_salary,
        severance_accrued=accrued_total,
    )

    out_exec = tool_execution.execute_tool_call(
        tool_name="EXECUTE_WORK_TERMINATION",
        args={
            "termination_date": end.isoformat(),
            "termination_reason": "layoff",
            "final_salary": last_salary,
            "calculate_severance": True,
        },
        client_id=client_id,
        db=db_session,
        pension_portfolio=None,
        user_approved=True,
    )
    payload_exec = _extract_tool_json(out_exec)
    sev_exec = (payload_exec.get("severance_calculated") or {})

    _approve_default_termination_preview(db_session, client_id=client_id, termination_date=end)
    out_proc = tool_execution.execute_tool_call(
        tool_name="PROCESS_TERMINATION",
        args={
            "termination_date": end.isoformat(),
            "exempt_choice": "redeem_with_exemption",
            "taxable_choice": "annuity",
            "confirmed": True,
        },
        client_id=client_id,
        db=db_session,
        pension_portfolio=[],
        user_approved=True,
    )
    payload_proc = _extract_tool_json(out_proc)
    details = (payload_proc.get("details") or {})

    assert abs(float(details.get("severance_amount") or 0) - float(sev_exec.get("severance_amount") or 0)) < 0.01
    assert abs(float(details.get("taxable_amount") or 0) - float(sev_exec.get("taxable_amount") or 0)) < 0.01
