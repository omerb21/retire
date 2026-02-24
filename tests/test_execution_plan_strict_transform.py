import json

from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.models.additional_income import AdditionalIncome
from app.models.client import Client
from app.models.pension_fund import PensionFund
from app.models.scenario import Scenario
from app.services.llm_agent_tools_service import AgentToolsService
from app.services.llm_chat.tool_handlers.transform_funds_to_assets_impl import (
    handle_transform_funds_to_assets,
)


def test_execution_plan_strict_transform_consumes_sources_and_skips_blocked(
    db_session,
) -> None:
    unique_id = f"exec-plan-{uuid4()}"
    client_obj = Client(
        id_number_raw=unique_id,
        id_number=unique_id,
        full_name="Exec Plan Test",
        birth_date=date(1980, 1, 1),
        gender="male",
        is_active=True,
        current_employer_exists=False,
    )
    db_session.add(client_obj)
    db_session.commit()
    db_session.refresh(client_obj)

    client_id = client_obj.id

    db_session.add(
        AdditionalIncome(
            client_id=client_id,
            source_type="other",
            description="External income",
            amount=Decimal("10000.00"),
            frequency="monthly",
            start_date=date(2020, 1, 1),
            end_date=None,
            indexation_method="none",
            fixed_rate=None,
            tax_treatment="fixed_rate",
            tax_rate=Decimal("10.00"),
            remarks=None,
        )
    )
    db_session.commit()

    portfolio = [
        {
            "מספר_חשבון": "A1",
            "שם_תכנית": "Plan A",
            "סוג_מוצר": "קופת גמל",
            "יתרה": 100000,
            "תגמולי_עובד_אחרי_2000": 100000,
            "פיצויים_שלא_עברו_התחשבנות": 50000,
            "specific_amounts": {
                "תגמולי_עובד_אחרי_2000": 100000,
                "פיצויים_שלא_עברו_התחשבנות": 50000,
            },
        }
    ]

    snapshot = Scenario(
        client_id=client_id,
        scenario_name="pension_portfolio_snapshot",
        apply_tax_planning=False,
        apply_capitalization=False,
        apply_exemption_shield=False,
        parameters=json.dumps({"pension_portfolio": portfolio}, ensure_ascii=False),
    )
    db_session.add(snapshot)

    source_pf = PensionFund(
        client_id=client_id,
        fund_name="Plan A",
        fund_type="קופת גמל",
        input_mode="manual",
        balance=100000.0,
        annuity_factor=200.0,
        pension_amount=500.0,
        pension_start_date=None,
        indexation_method="none",
        tax_treatment="taxable",
        deduction_file="A1",
        conversion_source=json.dumps(
            {
                "source": "pension_portfolio",
                "type": "pension_portfolio",
                "account_number": "A1",
            },
            ensure_ascii=False,
        ),
    )
    db_session.add(source_pf)
    db_session.commit()

    agent_tools = AgentToolsService(
        db=db_session,
        client_id=client_id,
        client_object=client_obj,
        pension_portfolio_data=portfolio,
    )

    plan = agent_tools.build_target_pension_plan(
        target_monthly_pension=30000.0,
        retirement_age=None,
        target_is_net=False,
        ignore_blocked_balances=True,
    )
    assert plan.get("success") is True, plan
    plan_res = plan.get("result") if isinstance(plan.get("result"), dict) else {}
    execution_plan = (
        plan_res.get("execution_plan")
        if isinstance(plan_res.get("execution_plan"), dict)
        else None
    )
    assert isinstance(execution_plan, dict)
    assert isinstance(execution_plan.get("accounts"), list)
    assert float(execution_plan.get("expected_total_gross") or 0) <= float(
        execution_plan.get("target_gross") or 0
    )

    transform_res_raw = handle_transform_funds_to_assets(
        args={
            "execution_plan": execution_plan,
            "accounts": [],
            "use_provided_accounts_only": True,
            "ignore_blocked_balances": True,
            "skip_non_convertible_accounts": True,
        },
        client_id=client_id,
        db=db_session,
        agent_tools=agent_tools,
    )
    transform_res = json.loads(transform_res_raw)
    assert transform_res.get("success") is True
    assert int(transform_res.get("source_pension_funds_zeroed") or 0) > 0

    db_session.refresh(source_pf)
    assert float(source_pf.balance or 0) == 0.0
    assert float(source_pf.pension_amount or 0) == 0.0

    updated = (
        db_session.query(Scenario)
        .filter(Scenario.client_id == client_id)
        .filter(Scenario.scenario_name == "pension_portfolio_snapshot")
        .order_by(Scenario.id.desc())
        .first()
    )
    params = json.loads(updated.parameters)
    updated_portfolio = params.get("pension_portfolio")
    assert isinstance(updated_portfolio, list)
    acc = updated_portfolio[0]
    assert float(acc.get("תגמולי_עובד_אחרי_2000") or 0) == 0.0
    assert float(acc.get("פיצויים_שלא_עברו_התחשבנות") or 0) > 0.0
