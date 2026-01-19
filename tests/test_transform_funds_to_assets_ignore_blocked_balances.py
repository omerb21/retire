import json

from app.models.capital_asset import CapitalAsset
from app.models.pension_fund import PensionFund
from app.services.llm_agent_tools_service import AgentToolsService
from app.services.llm_chat.tool_handlers.transform_funds_to_assets import (
    handle_transform_funds_to_assets,
)


def test_transform_ignores_blocked_and_skips_employer_current_severance(db_session, client) -> None:
    account_number = "ACC-BLOCK-1"

    # Clean prior conversions for this account
    db_session.query(CapitalAsset).filter(
        CapitalAsset.client_id == client.id,
        CapitalAsset.conversion_source.isnot(None),
        CapitalAsset.conversion_source.like(f'%"account_number": "{account_number}"%'),
    ).delete(synchronize_session=False)

    db_session.query(PensionFund).filter(
        PensionFund.client_id == client.id,
        PensionFund.deduction_file == account_number,
    ).delete(synchronize_session=False)
    db_session.commit()

    agent_tools = AgentToolsService(db=db_session, client_id=client.id, client_object=client)

    blocked_unresolved = 1111.0
    blocked_rights = 2222.0
    employer_current = 3333.0
    convertible_after_settlement = 4444.0

    result_str = handle_transform_funds_to_assets(
        args={
            "accounts": [
                {
                    "account_name": "Mixed Account",
                    "product_type": "ביטוח מנהלים",
                    "company": "TestCo",
                    "account_number": account_number,
                    "specific_amounts": {
                        "פיצויים_שלא_עברו_התחשבנות": blocked_unresolved,
                        "פיצויים_ממעסיקים_קודמים_רצף_זכויות": blocked_rights,
                        "פיצויים_מעסיק_נוכחי": employer_current,
                        "פיצויים_לאחר_התחשבנות": convertible_after_settlement,
                    },
                    "balance": blocked_unresolved
                    + blocked_rights
                    + employer_current
                    + convertible_after_settlement,
                }
            ],
            "ignore_blocked_balances": True,
            "skip_non_convertible_accounts": True,
            "use_provided_accounts_only": True,
        },
        client_id=client.id,
        db=db_session,
        agent_tools=agent_tools,
    )

    payload = json.loads(result_str)
    assert payload["success"] is True

    # Blocked fields should be ignored and reported.
    assert float(payload.get("ignored_blocked_amount") or 0) == blocked_unresolved + blocked_rights

    # Current employer severance should be skipped and reported.
    assert float(payload.get("employer_current_severance_not_converted") or 0) == employer_current

    skipped_items = payload.get("skipped_items") or []
    assert any(
        item.get("field") == "פיצויים_מעסיק_נוכחי" and float(item.get("amount") or 0) == employer_current
        for item in skipped_items
    )

    # Only the convertible component should be converted into an asset.
    assert payload.get("total_converted") == 1

    created_pf = (
        db_session.query(PensionFund)
        .filter(
            PensionFund.client_id == client.id,
            PensionFund.deduction_file == account_number,
            PensionFund.conversion_source.isnot(None),
            PensionFund.conversion_source.like('%"source": "llm_transform_funds_to_assets"%'),
        )
        .first()
    )

    created_ca = (
        db_session.query(CapitalAsset)
        .filter(
            CapitalAsset.client_id == client.id,
            CapitalAsset.conversion_source.isnot(None),
            CapitalAsset.conversion_source.like('%"source": "llm_transform_funds_to_assets"%'),
            CapitalAsset.conversion_source.like(f'%"account_number": "{account_number}"%'),
        )
        .first()
    )

    assert (created_pf is not None) or (created_ca is not None)

    if created_pf is not None:
        assert float(created_pf.balance or 0) == convertible_after_settlement
    if created_ca is not None:
        assert float(created_ca.current_value or 0) == convertible_after_settlement
        assert float(created_ca.monthly_income or 0) == 0.0
