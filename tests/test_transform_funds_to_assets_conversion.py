import json
from datetime import date

from app.models.capital_asset import CapitalAsset
from app.models.pension_fund import PensionFund
from app.models.scenario import Scenario
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


def test_transform_creates_capital_assets_with_current_value(db_session, client) -> None:
    account_number = "ACC-API-CAP-1"
    db_session.query(CapitalAsset).filter(
        CapitalAsset.client_id == client.id,
        CapitalAsset.conversion_source.isnot(None),
        CapitalAsset.conversion_source.like(f'%"account_number": "{account_number}"%'),
    ).delete(synchronize_session=False)
    db_session.commit()

    agent_tools = AgentToolsService(db=db_session, client_id=client.id, client_object=client)
    result_str = handle_transform_funds_to_assets(
        args={
            "accounts": [
                {
                    "account_name": "API Capital",
                    "product_type": "קרן השתלמות",
                    "company": "TestCo",
                    "account_number": account_number,
                    "specific_amounts": {"קרן_השתלמות": 100000.0},
                }
            ],
            "pension_start_date": "2047-01-01",
            "use_provided_accounts_only": True,
        },
        client_id=client.id,
        db=db_session,
        agent_tools=agent_tools,
    )
    payload = json.loads(result_str)
    assert payload["success"] is True

    resp = client.get(f"/api/v1/clients/{client.id}/capital-assets/")
    assert resp.status_code == 200
    assets = resp.json()
    assert isinstance(assets, list)

    created = [
        a
        for a in assets
        if isinstance(a, dict)
        and str(a.get("conversion_source") or "").find(account_number) >= 0
        and str(a.get("conversion_source") or "").find("llm_transform_funds_to_assets") >= 0
    ]
    assert created

    for a in created:
        assert float(a.get("current_value") or 0) > 0
        assert float(a.get("monthly_income") or 0) == 0


def test_transform_reduces_pension_portfolio_components(db_session, client) -> None:
    account_number = "ACC-API-SNAP-1"

    db_session.query(Scenario).filter(
        Scenario.client_id == client.id,
        Scenario.scenario_name == "pension_portfolio_snapshot",
    ).delete(synchronize_session=False)
    db_session.commit()

    portfolio = [
        {
            "מספר_חשבון": account_number,
            "שם_תכנית": "כלל תמר",
            "סוג_מוצר": "קופת גמל",
            "יתרה": 100000.0,
            "תגמולי_עובד_אחרי_2000": 40000.0,
            "תגמולי_מעביד_אחרי_2000": 60000.0,
            "specific_amounts": {
                "תגמולי_עובד_אחרי_2000": 40000.0,
                "תגמולי_מעביד_אחרי_2000": 60000.0,
            },
        }
    ]
    snapshot = Scenario(
        client_id=client.id,
        scenario_name="pension_portfolio_snapshot",
        apply_tax_planning=False,
        apply_capitalization=False,
        apply_exemption_shield=False,
        parameters=json.dumps({"pension_portfolio": portfolio}, ensure_ascii=False),
    )
    db_session.add(snapshot)
    db_session.commit()

    agent_tools = AgentToolsService(db=db_session, client_id=client.id, client_object=client)
    result_str = handle_transform_funds_to_assets(
        args={
            "accounts": [
                {
                    "account_name": "כלל תמר",
                    "product_type": "קופת גמל",
                    "company": "TestCo",
                    "account_number": account_number,
                    "specific_amounts": {
                        "תגמולי_עובד_אחרי_2000": 40000.0,
                        "תגמולי_מעביד_אחרי_2000": 60000.0,
                    },
                }
            ],
            "pension_start_date": "2047-01-01",
            "use_provided_accounts_only": True,
        },
        client_id=client.id,
        db=db_session,
        agent_tools=agent_tools,
    )
    payload = json.loads(result_str)
    assert payload["success"] is True

    resp = client.get(f"/api/v1/clients/{client.id}/pension-portfolio/")
    assert resp.status_code == 200
    updated = resp.json()
    assert isinstance(updated, list)
    row = next((r for r in updated if isinstance(r, dict) and r.get("מספר_חשבון") == account_number), None)
    assert row is not None
    assert float(row.get("יתרה") or 0) == 0.0
    assert float(row.get("תגמולי_עובד_אחרי_2000") or 0) == 0.0
    assert float(row.get("תגמולי_מעביד_אחרי_2000") or 0) == 0.0
    assert isinstance(row.get("specific_amounts"), dict)
    assert float(row["specific_amounts"].get("תגמולי_עובד_אחרי_2000") or 0) == 0.0
    assert float(row["specific_amounts"].get("תגמולי_מעביד_אחרי_2000") or 0) == 0.0


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


def test_transform_pension_does_not_zero_tool_created_pension_fund(db_session, client) -> None:
    account_number = "ACC-PEN-1"
    amount = 100000.0

    db_session.query(PensionFund).filter(
        PensionFund.client_id == client.id,
        PensionFund.deduction_file == account_number,
    ).delete(synchronize_session=False)
    db_session.commit()

    source_pf = PensionFund(
        client_id=client.id,
        fund_name="Source Portfolio Fund",
        fund_type="קרן פנסיה",
        input_mode="manual",
        balance=amount,
        annuity_factor=200.0,
        pension_amount=0.0,
        pension_start_date=None,
        indexation_method="none",
        tax_treatment="taxable",
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
                    "account_name": "Converted Pension",
                    "product_type": "קרן פנסיה",
                    "company": "TestCo",
                    "account_number": account_number,
                    "specific_amounts": {
                        "תגמולי_עובד_אחרי_2000": amount,
                    },
                }
            ],
            "pension_start_date": "2047-01-01",
        },
        client_id=client.id,
        db=db_session,
        agent_tools=agent_tools,
    )

    payload = json.loads(result_str)
    assert payload["success"] is True
    assert payload.get("converted_pensions") == 1

    converted_pf = (
        db_session.query(PensionFund)
        .filter(
            PensionFund.client_id == client.id,
            PensionFund.deduction_file == account_number,
            PensionFund.conversion_source.isnot(None),
            PensionFund.conversion_source.like('%"source": "llm_transform_funds_to_assets"%'),
        )
        .first()
    )
    assert converted_pf is not None
    assert float(converted_pf.balance or 0) > 0.0

    db_session.refresh(source_pf)
    assert float(source_pf.balance or 0) == 0.0


def test_transform_updates_snapshot_scenario_zeroes_converted_components(db_session, client) -> None:
    account_number = "ACC-SNAP-1"

    db_session.query(Scenario).filter(
        Scenario.client_id == client.id,
        Scenario.scenario_name == "pension_portfolio_snapshot",
    ).delete(synchronize_session=False)
    db_session.commit()

    initial_portfolio = [
        {
            "מספר_חשבון": account_number,
            "שם_תכנית": "כלל תמר",
            "סוג_מוצר": "קופת גמל",
            "יתרה": 100.0,
            "תגמולי_עובד_אחרי_2008_לא_משלמת": 40.0,
            "תגמולי_מעביד_אחרי_2008_לא_משלמת": 60.0,
        }
    ]
    snapshot = Scenario(
        client_id=client.id,
        scenario_name="pension_portfolio_snapshot",
        apply_tax_planning=False,
        apply_capitalization=False,
        apply_exemption_shield=False,
        parameters=json.dumps({"pension_portfolio": initial_portfolio}, ensure_ascii=False),
    )
    db_session.add(snapshot)
    db_session.commit()

    agent_tools = AgentToolsService(db=db_session, client_id=client.id, client_object=client)
    result_str = handle_transform_funds_to_assets(
        args={
            "accounts": [
                {
                    "account_name": "כלל תמר",
                    "product_type": "קופת גמל",
                    "company": "TestCo",
                    "account_number": account_number,
                    "specific_amounts": {
                        "תגמולי_עובד_אחרי_2008_לא_משלמת": 40.0,
                        "תגמולי_מעביד_אחרי_2008_לא_משלמת": 60.0,
                    },
                }
            ],
            "pension_start_date": "2047-01-01",
        },
        client_id=client.id,
        db=db_session,
        agent_tools=agent_tools,
    )

    payload = json.loads(result_str)
    assert payload["success"] is True
    assert int(payload.get("persisted_source_scenarios_updated") or 0) == 1
    assert payload.get("persisted_source_cleanup_ok") in (True, 1)

    latest_snapshot = (
        db_session.query(Scenario)
        .filter(Scenario.client_id == client.id)
        .filter(Scenario.scenario_name == "pension_portfolio_snapshot")
        .order_by(Scenario.created_at.desc())
        .first()
    )
    assert latest_snapshot is not None
    latest_params = json.loads(latest_snapshot.parameters)
    latest_portfolio = latest_params.get("pension_portfolio")
    assert isinstance(latest_portfolio, list) and latest_portfolio
    row = next((r for r in latest_portfolio if r.get("מספר_חשבון") == account_number), None)
    assert row is not None
    assert float(row.get("יתרה") or 0) == 0.0
    assert float(row.get("תגמולי_עובד_אחרי_2008_לא_משלמת") or 0) == 0.0
    assert float(row.get("תגמולי_מעביד_אחרי_2008_לא_משלמת") or 0) == 0.0


def test_transform_updates_snapshot_scenario_zeroes_education_fund_even_when_edu_field_missing(
    db_session, client
) -> None:
    account_number = "ACC-EDU-SNAP-1"

    db_session.query(Scenario).filter(
        Scenario.client_id == client.id,
        Scenario.scenario_name == "pension_portfolio_snapshot",
    ).delete(synchronize_session=False)
    db_session.commit()

    # Simulate a common real-world case:
    # - product is קרן השתלמות
    # - snapshot may store tagmulim/total fields, but may NOT include a dedicated קרן_השתלמות key
    initial_portfolio = [
        {
            "מספר_חשבון": account_number,
            "שם_תכנית": "מיטב השתלמות",
            "סוג_מוצר": "קרן השתלמות",
            "יתרה": 1000.0,
            "תגמולים": 1000.0,
            "סך_תגמולים": 1000.0,
            "תגמולי_עובד_אחרי_2008_לא_משלמת": 300.0,
            "תגמולי_מעביד_אחרי_2008_לא_משלמת": 700.0,
        }
    ]
    snapshot = Scenario(
        client_id=client.id,
        scenario_name="pension_portfolio_snapshot",
        apply_tax_planning=False,
        apply_capitalization=False,
        apply_exemption_shield=False,
        parameters=json.dumps({"pension_portfolio": initial_portfolio}, ensure_ascii=False),
    )
    db_session.add(snapshot)
    db_session.commit()

    agent_tools = AgentToolsService(db=db_session, client_id=client.id, client_object=client)
    result_str = handle_transform_funds_to_assets(
        args={
            "accounts": [
                {
                    "account_name": "מיטב השתלמות",
                    "product_type": "קרן השתלמות",
                    "company": "TestCo",
                    "account_number": account_number,
                    "specific_amounts": {
                        "קרן_השתלמות": 1000.0,
                    },
                }
            ],
            "pension_start_date": "2047-01-01",
        },
        client_id=client.id,
        db=db_session,
        agent_tools=agent_tools,
    )

    payload = json.loads(result_str)
    assert payload["success"] is True
    assert int(payload.get("persisted_source_scenarios_updated") or 0) == 1

    latest_snapshot = (
        db_session.query(Scenario)
        .filter(Scenario.client_id == client.id)
        .filter(Scenario.scenario_name == "pension_portfolio_snapshot")
        .order_by(Scenario.created_at.desc())
        .first()
    )
    assert latest_snapshot is not None
    latest_params = json.loads(latest_snapshot.parameters)
    latest_portfolio = latest_params.get("pension_portfolio")
    assert isinstance(latest_portfolio, list) and latest_portfolio
    row = next((r for r in latest_portfolio if r.get("מספר_חשבון") == account_number), None)
    assert row is not None
    assert float(row.get("יתרה") or 0) == 0.0
    assert float(row.get("קרן_השתלמות") or 0) == 0.0
    assert float(row.get("תגמולים") or 0) == 0.0
    assert float(row.get("סך_תגמולים") or 0) == 0.0
    assert float(row.get("תגמולי_עובד_אחרי_2008_לא_משלמת") or 0) == 0.0
    assert float(row.get("תגמולי_מעביד_אחרי_2008_לא_משלמת") or 0) == 0.0


def test_transform_tagmulim_to_2000_capital_is_exempt(db_session, client) -> None:
    account_number = "ACC-2000-EXEMPT"

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
                    "account_name": "Tagmulim <2000",
                    "product_type": "קופת גמל",
                    "company": "TestCo",
                    "account_number": account_number,
                    "specific_amounts": {
                        "תגמולי_עובד_עד_2000": 50000.0,
                    },
                }
            ],
            "pension_start_date": "2047-01-01",
        },
        client_id=client.id,
        db=db_session,
        agent_tools=agent_tools,
    )

    payload = json.loads(result_str)
    assert payload["success"] is True
    assert int(payload.get("converted_capitals") or 0) == 1

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
    assert ca.tax_treatment == "exempt"
