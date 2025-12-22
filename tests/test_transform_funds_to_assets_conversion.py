import json
from datetime import date

from app.models.capital_asset import CapitalAsset
from app.models.pension_fund import PensionFund
from app.providers.tax_params import InMemoryTaxParamsProvider
from app.services.capital_asset.service import CapitalAssetService
from app.services.llm_agent_tools_service import AgentToolsService
from app.services.llm_chat.tool_handlers.transform_funds_to_assets import (
    handle_transform_funds_to_assets,
)


def test_transform_capital_asset_and_zero_source_and_cashflow(db_session, client) -> None:
    account_number = "ACC123"

    db_session.query(CapitalAsset).filter(
        CapitalAsset.client_id == client.id,
        CapitalAsset.conversion_source.isnot(None),
        CapitalAsset.conversion_source.like(f'%"account_number": "{account_number}"%'),
    ).delete(synchronize_session=False)

    db_session.query(PensionFund).filter(
        PensionFund.client_id == client.id,
        PensionFund.deduction_file == account_number,
    ).delete(synchronize_session=False)

    source_pf = PensionFund(
        client_id=client.id,
        fund_name="Imported Portfolio Fund",
        fund_type="קרן השתלמות",
        input_mode="manual",
        balance=100000.0,
        annuity_factor=200.0,
        pension_amount=None,
        pension_start_date=None,
        indexation_method="none",
        tax_treatment="exempt",
        deduction_file=account_number,
        conversion_source=json.dumps(
            {
                "type": "pension_portfolio",
                "source": "pension_portfolio",
                "account_number": account_number,
            },
            ensure_ascii=False,
        ),
    )
    db_session.add(source_pf)
    db_session.commit()

    agent_tools = AgentToolsService(db=db_session, client_id=client.id, client_object=client)

    result_str = handle_transform_funds_to_assets(
        args={
            "accounts": [
                {
                    "account_name": "Converted Capital",
                    "balance": 100000,
                    "product_type": "קרן השתלמות",
                    "company": "TestCo",
                    "account_number": account_number,
                    "conversion_type": "capital_asset",
                }
            ]
        },
        client_id=client.id,
        db=db_session,
        agent_tools=agent_tools,
    )

    payload = json.loads(result_str)
    assert payload["success"] is True

    ca = (
        db_session.query(CapitalAsset)
        .filter(
            CapitalAsset.client_id == client.id,
            CapitalAsset.conversion_source.isnot(None),
            CapitalAsset.conversion_source.like(f'%"account_number": "{account_number}"%'),
        )
        .first()
    )
    assert ca is not None

    assert float(ca.current_value or 0) == 100000.0
    assert float(ca.monthly_income or 0) == 0.0
    assert ca.start_date == date(2047, 1, 1)

    db_session.refresh(source_pf)
    assert float(source_pf.balance or 0) == 0.0
    assert float(source_pf.pension_amount or 0) == 0.0

    asset_service = CapitalAssetService(InMemoryTaxParamsProvider())
    cashflow = asset_service.generate_combined_cashflow(
        db_session=db_session,
        client_id=client.id,
        start_date=date(2047, 1, 1),
        end_date=date(2047, 1, 1),
        reference_date=date(2047, 1, 1),
    )

    assert len(cashflow) == 1
    assert float(cashflow[0]["gross_return"]) == 100000.0
    assert float(cashflow[0]["net_return"]) == 100000.0


def test_transform_does_not_convert_current_employer_severance_via_tagmulim(db_session, client) -> None:
    account_number = "ACC-SEV-1"
    severance_amount = 12345.0

    db_session.query(CapitalAsset).filter(
        CapitalAsset.client_id == client.id,
        CapitalAsset.conversion_source.isnot(None),
        CapitalAsset.conversion_source.like(f'%"account_number": "{account_number}"%'),
    ).delete(synchronize_session=False)

    db_session.query(PensionFund).filter(
        PensionFund.client_id == client.id,
        PensionFund.deduction_file == account_number,
    ).delete(synchronize_session=False)

    agent_tools = AgentToolsService(db=db_session, client_id=client.id, client_object=client)

    result_str = handle_transform_funds_to_assets(
        args={
            "accounts": [
                {
                    "account_name": "Severance Only",
                    "balance": severance_amount,
                    "product_type": "קרן פנסיה",
                    "company": "TestCo",
                    "account_number": account_number,
                    "specific_amounts": {
                        "פיצויים_מעסיק_נוכחי": severance_amount,
                        "תגמולים": severance_amount,
                    },
                }
            ]
        },
        client_id=client.id,
        db=db_session,
        agent_tools=agent_tools,
    )

    payload = json.loads(result_str)
    assert payload["success"] is True
    assert payload.get("total_converted") == 0
    assert payload.get("converted_items") in (None, [])

    skipped_items = payload.get("skipped_items") or []
    assert any(
        item.get("field") == "פיצויים_מעסיק_נוכחי" and float(item.get("amount") or 0) == severance_amount
        for item in skipped_items
    )
    assert float(payload.get("employer_current_severance_not_converted") or 0) == severance_amount

    ca = (
        db_session.query(CapitalAsset)
        .filter(
            CapitalAsset.client_id == client.id,
            CapitalAsset.conversion_source.isnot(None),
            CapitalAsset.conversion_source.like(f'%"account_number": "{account_number}"%'),
        )
        .first()
    )
    assert ca is None

    pf = (
        db_session.query(PensionFund)
        .filter(
            PensionFund.client_id == client.id,
            PensionFund.deduction_file == account_number,
        )
        .first()
    )
    assert pf is None
