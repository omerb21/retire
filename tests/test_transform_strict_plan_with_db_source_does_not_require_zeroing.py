import json
from datetime import date

from app.models.client import Client
from app.models.pension_fund import PensionFund
from app.services.llm_chat.tool_execution import execute_tool_call


def test_transform_strict_plan_with_db_source_does_not_require_zeroing(_test_db) -> None:
    """Regression: strict plan execution should not fail-fast when there is no portfolio-source row to zero.

    This models the real case:
    - DB has a PensionFund (not imported from pension_portfolio) with deduction_file=account_number.
    - Execution plan requests a partial conversion for that account.
    - Pipeline should create/update the LLM-converted PensionFund row and commit.
    """

    Session = _test_db["Session"]
    client_id = 995000888

    with Session() as db:
        client = db.query(Client).filter(Client.id == client_id).first()
        if client is None:
            client = Client(
                id=client_id,
                id_number_raw=str(client_id),
                id_number=str(client_id),
                full_name="Test User",
                birth_date=date(1980, 1, 1),
                gender="male",
                is_active=True,
            )
            db.add(client)
            db.flush()

        # Seed a DB pension fund that is NOT a portfolio-imported row (conversion_source=None)
        db.add(
            PensionFund(
                client_id=client_id,
                fund_name="494930",
                fund_type="קופת גמל",
                input_mode="manual",
                balance=594_647.65,
                annuity_factor=200,
                pension_amount=0,
                tax_treatment="taxable",
                deduction_file="494930",
                conversion_source=None,
            )
        )
        db.commit()

    # Execute tool deterministically (same tool path used by approvals).
    args = {
        "execution_plan": {
            "target_net": 0,
            "target_gross": 0,
            "accounts": [
                {
                    "account_id": "494930",
                    "component": "תגמולים_עובד_אחרי_2000",
                    "amount_to_convert": 1000.0,
                    "expected_monthly_pension": 10.0,
                }
            ],
        },
        "use_provided_accounts_only": True,
        "ignore_blocked_balances": True,
        "skip_non_convertible_accounts": True,
    }

    with Session() as db:
        res = execute_tool_call(
            tool_name="TRANSFORM_FUNDS_TO_ASSETS",
            args=args,
            client_id=client_id,
            db=db,
            pension_portfolio=[],
            user_approved=True,
        )

    assert isinstance(res, str)
    assert "EXECUTION_NO_SOURCE_CONSUMED" not in res

    # Ensure a converted pension fund row exists after execution.
    with Session() as db:
        converted = (
            db.query(PensionFund)
            .filter(PensionFund.client_id == client_id)
            .filter(PensionFund.conversion_source.isnot(None))
            .all()
        )
        assert len(converted) > 0
