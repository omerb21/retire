from datetime import date

from app.models.client import Client
from app.models.pension_fund import PensionFund
from app.services.pension_fund_service import get_existing_monthly_pension_gross


def test_get_existing_monthly_pension_gross_sums_only_katzba_prefix(db_session) -> None:
    client_obj = Client(
        id_number_raw="svc-1",
        id_number="svc-1",
        full_name="Service Test",
        birth_date=date(1980, 1, 1),
        gender="male",
        is_active=True,
        current_employer_exists=False,
    )
    db_session.add(client_obj)
    db_session.commit()
    db_session.refresh(client_obj)

    client_id = int(client_obj.id)

    db_session.add(
        PensionFund(
            client_id=client_id,
            fund_name="קצבה ממענק פיצויים חייב - Plan (Emp)",
            fund_type="monthly_pension",
            input_mode="manual",
            balance=0.0,
            annuity_factor=200.0,
            pension_amount=1000.0,
            pension_start_date=None,
            indexation_method="none",
            tax_treatment="taxable",
            deduction_file="S1",
            remarks=None,
            conversion_source=None,
        )
    )
    db_session.add(
        PensionFund(
            client_id=client_id,
            fund_name="קצבה אחרת",
            fund_type="monthly_pension",
            input_mode="manual",
            balance=0.0,
            annuity_factor=200.0,
            pension_amount=250.0,
            pension_start_date=None,
            indexation_method="none",
            tax_treatment="taxable",
            deduction_file="S2",
            remarks=None,
            conversion_source=None,
        )
    )
    db_session.add(
        PensionFund(
            client_id=client_id,
            fund_name="Existing Pension",
            fund_type="monthly_pension",
            input_mode="manual",
            balance=0.0,
            annuity_factor=200.0,
            pension_amount=9999.0,
            pension_start_date=None,
            indexation_method="none",
            tax_treatment="taxable",
            deduction_file="S3",
            remarks=None,
            conversion_source=None,
        )
    )
    db_session.commit()

    total = get_existing_monthly_pension_gross(db_session, client_id)
    assert float(total) == 1250.0
