import json
from datetime import date

import app.services.llm_chat.tool_execution as tool_execution
from app.models.client import Client
from app.models.current_employment.employer import CurrentEmployer
from app.services.llm_chat.orchestration_utils_parts.blocked_balances_policy import (
    store_current_employer_termination_plan_preview,
)


def test_process_termination_tool_preserves_manual_amounts(db_session) -> None:
    client_id = 990000001

    client = db_session.query(Client).filter(Client.id == client_id).first()
    if client is None:
        client = Client(
            id=client_id,
            id_number_raw=str(client_id),
            id_number=str(client_id),
            full_name="Manual Amounts Tool Test",
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
            employer_name="Manual Employer",
            start_date=date(2020, 1, 1),
            end_date=None,
            last_salary=10000.0,
            severance_accrued=0.0,
        )
        db_session.add(employer)
        db_session.flush()

    term_date = date(2025, 1, 1)
    store_current_employer_termination_plan_preview(
        db=db_session,
        client_id=int(client.id),
        payload={
            "termination_arguments_template": {
                "confirmed": True,
                "termination_date": term_date.isoformat(),
                "exempt_choice": "redeem_with_exemption",
                "taxable_choice": "annuity",
                "severance_amount": 10000,
                "exempt_amount": 2500,
            },
            "awaiting_user_confirmation": False,
            "approved": True,
            "declined": False,
            "used": False,
        },
    )

    out = tool_execution.execute_tool_call(
        tool_name="PROCESS_TERMINATION",
        args={"confirmed": True, "exempt_choice": "annuity", "taxable_choice": "annuity"},
        client_id=int(client.id),
        db=db_session,
        pension_portfolio=[],
        user_approved=True,
    )

    parsed = json.loads(out.split("###SEVERANCE_RESET###", 1)[0])
    details = parsed.get("details") or {}

    assert abs(float(details.get("severance_amount") or 0) - 10000.0) < 0.01
    assert abs(float(details.get("exempt_amount") or 0) - 2500.0) < 0.01
    assert abs(float(details.get("taxable_amount") or 0) - 7500.0) < 0.01
