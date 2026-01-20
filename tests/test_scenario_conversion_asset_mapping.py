import json

from app.models.capital_asset import CapitalAsset
from app.models.pension_fund import PensionFund
from app.services.retirement.utils.capital_utils import create_capital_asset_from_pension
from app.services.retirement.utils.pension_utils import convert_education_fund_to_capital


def test_scenario_conversion_commutation_asset_is_lump_sum(db_session, client) -> None:
    pf = PensionFund(
        client_id=client.id,
        fund_name="Scenario Commutation Fund",
        fund_type="קרן פנסיה",
        input_mode="manual",
        balance=0.0,
        annuity_factor=200.0,
        pension_amount=1000.0,
        pension_start_date=None,
        indexation_method="none",
        tax_treatment="taxable",
        deduction_file="SCEN-COMM-1",
        conversion_source=json.dumps(
            {
                "type": "pension_portfolio",
                "source": "pension_portfolio",
                "account_number": "SCEN-COMM-1",
                "original_balance": 100000.0,
                "specific_amounts": {"תגמולי_עובד_אחרי_2000": 100000.0},
            },
            ensure_ascii=False,
        ),
    )
    db_session.add(pf)
    db_session.commit()

    ca = create_capital_asset_from_pension(
        pf,
        client_id=client.id,
        retirement_year=2047,
        partial=False,
        add_action_callback=None,
    )
    assert ca is not None
    db_session.add(ca)
    db_session.commit()

    created = (
        db_session.query(CapitalAsset)
        .filter(
            CapitalAsset.client_id == client.id,
            CapitalAsset.conversion_source.isnot(None),
            CapitalAsset.conversion_source.like('%"source": "scenario_conversion"%'),
        )
        .order_by(CapitalAsset.id.desc())
        .first()
    )
    assert created is not None

    assert float(created.current_value or 0) > 0
    assert float(created.monthly_income or 0) == 0.0
    assert created.payment_frequency == "annually"


def test_scenario_conversion_education_fund_asset_current_value_equals_original_balance(db_session, client) -> None:
    ef = PensionFund(
        client_id=client.id,
        fund_name="Scenario Education Fund",
        fund_type="קרן השתלמות",
        input_mode="manual",
        balance=199165.19,
        annuity_factor=200.0,
        pension_amount=None,
        pension_start_date=None,
        indexation_method="none",
        tax_treatment="exempt",
        deduction_file="SCEN-EF-1",
        conversion_source=json.dumps(
            {
                "type": "pension_portfolio",
                "source": "pension_portfolio",
                "account_number": "SCEN-EF-1",
                "original_balance": 199165.19,
                "specific_amounts": {"קרן_השתלמות": 199165.19},
            },
            ensure_ascii=False,
        ),
    )
    db_session.add(ef)
    db_session.commit()

    ca = convert_education_fund_to_capital(
        ef,
        client_id=client.id,
        retirement_year=2047,
        add_action_callback=None,
    )
    assert ca is not None
    db_session.add(ca)
    db_session.commit()

    created = (
        db_session.query(CapitalAsset)
        .filter(
            CapitalAsset.client_id == client.id,
            CapitalAsset.conversion_source.isnot(None),
            CapitalAsset.conversion_source.like('%"source": "scenario_conversion"%'),
            CapitalAsset.asset_type == "education_fund",
        )
        .order_by(CapitalAsset.id.desc())
        .first()
    )
    assert created is not None

    assert float(created.monthly_income or 0) == 0.0

    src = json.loads(created.conversion_source or "{}")
    assert float(created.current_value or 0) == float(src.get("original_balance") or 0)
