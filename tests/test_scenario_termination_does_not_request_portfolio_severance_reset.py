from datetime import date

from app.models.client import Client
from app.models.current_employment import CurrentEmployer
from app.schemas.current_employer import TerminationDecisionCreate
from app.services.current_employer.termination import TerminationService


def test_process_termination_reset_flag_false_when_reset_severance_balance_false(
    db_session,
) -> None:
    client_id = 993000001

    client = db_session.query(Client).filter(Client.id == client_id).first()
    if client is None:
        client = Client(
            id=client_id,
            id_number_raw=str(client_id),
            id_number=str(client_id),
            full_name="Reset Flag",
            birth_date=date(1980, 1, 1),
            gender="male",
            is_active=True,
            current_employer_exists=True,
        )
        db_session.add(client)
        db_session.flush()

    employer = CurrentEmployer(
        client_id=client_id,
        employer_name="Employer",
        start_date=date(2020, 1, 1),
        end_date=None,
        last_salary=10000.0,
        severance_accrued=None,
        other_grants={},
    )
    db_session.add(employer)
    db_session.commit()

    decision = TerminationDecisionCreate(
        use_employer_completion=True,
        termination_date=date(2025, 12, 31),
        severance_amount=1000.0,
        exempt_amount=1000.0,
        taxable_amount=0.0,
        exempt_choice="redeem_with_exemption",
        taxable_choice="annuity",
        tax_spread_years=1,
        max_spread_years=1,
        confirmed=True,
    )

    service = TerminationService(db_session)
    result = service.process_termination(
        client,
        employer,
        decision,
        reset_severance_balance=False,
    )

    reset_info = result.get("severance_reset_info") or {}
    assert reset_info.get("portfolio_severance_to_reset") is False
