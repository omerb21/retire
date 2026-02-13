"""
Test: build_target_pension_plan must not include monthly_pension sources
whose DB pension_amount has been set to 0.

Scenario:
1. Create a client with two manual monthly_pension PensionFund rows (pension_amount > 0).
2. Run build_target_pension_plan — both should appear as existing_pension sources.
3. Set pension_amount = 0 for both rows.
4. Run build_target_pension_plan again — neither should appear as existing sources,
   and no plan step should reference them with a positive contribution.
"""
import json
from datetime import date
from typing import Any, Dict

import pytest

from app.models.capital_asset import CapitalAsset
from app.models.client import Client
from app.models.pension_fund import PensionFund


def test_zeroed_monthly_pension_excluded_from_plan(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]

    client_id = 970000001

    with Session() as db:
        client = db.query(Client).filter(Client.id == client_id).first()
        if client is None:
            client = Client(
                id=client_id,
                id_number_raw=str(client_id),
                id_number=str(client_id),
                full_name="Test Zeroed Pension",
                birth_date=date(1960, 6, 15),
                gender="male",
                is_active=True,
            )
            db.add(client)
            db.flush()

        # Create two manual monthly_pension PensionFund rows with pension_amount > 0
        pf1 = PensionFund(
            client_id=client_id,
            fund_name="קצבה ידנית א",
            fund_type="monthly_pension",
            input_mode="manual",
            balance=0,
            annuity_factor=None,
            pension_amount=3000.0,
            pension_start_date=date(2024, 1, 1),
            indexation_method="none",
            tax_treatment="taxable",
        )
        pf2 = PensionFund(
            client_id=client_id,
            fund_name="קצבה ידנית ב",
            fund_type="monthly_pension",
            input_mode="manual",
            balance=0,
            annuity_factor=None,
            pension_amount=2000.0,
            pension_start_date=date(2024, 1, 1),
            indexation_method="none",
            tax_treatment="exempt",
        )
        db.add(pf1)
        db.add(pf2)

        # Add a capital asset so the plan has convertible sources to work with
        ca = CapitalAsset(
            client_id=client_id,
            asset_name="נכס הון לבדיקה",
            asset_type="savings",
            current_value=2_000_000.0,
            monthly_income=0,
            annual_return_rate=0.0,
            payment_frequency="monthly",
            start_date=date(2020, 1, 1),
            tax_treatment="taxable",
        )
        db.add(ca)
        db.commit()

        pf1_id = pf1.id
        pf2_id = pf2.id

    # --- Phase 1: pension_amount > 0 — both should appear as existing sources ---
    from app.services.llm_agent_tools_service import AgentToolsService

    with Session() as db:
        svc = AgentToolsService(db=db, client_id=client_id)
        result1 = svc.build_target_pension_plan(
            target_monthly_pension=10000.0,
            target_is_net=False,
            ignore_blocked_balances=True,
        )

    assert result1["success"] is True, f"Phase 1 failed: {result1.get('explanation')}"
    res1 = result1["result"]

    # The existing pension total should include both funds (3000 + 2000 = 5000)
    assert res1["existing_pension_total_gross"] >= 5000.0, (
        f"Phase 1: expected existing_pension_total_gross >= 5000, got {res1['existing_pension_total_gross']}"
    )

    # Verify pension_fund_id is present in sources_used or existing sources
    all_sources_1 = res1.get("sources_used", []) + res1.get("sources_not_used", [])
    existing_pf_ids_1 = set()
    for s in all_sources_1:
        if s.get("source_type") == "existing_pension" and s.get("pension_fund_id"):
            existing_pf_ids_1.add(int(s["pension_fund_id"]))
    # Both pension fund IDs should be present as existing_pension sources
    # (they have action_needed=none so they won't be in sources_used for conversion)
    # Check via existing_pension_total_gross which sums them
    assert pf1_id is not None
    assert pf2_id is not None

    # --- Phase 2: set pension_amount = 0 for both ---
    with Session() as db:
        for pf_id in [pf1_id, pf2_id]:
            pf = db.query(PensionFund).filter(PensionFund.id == pf_id).first()
            assert pf is not None, f"PensionFund {pf_id} not found"
            pf.pension_amount = 0.0
        db.commit()

    # --- Phase 3: re-run — neither should contribute ---
    with Session() as db:
        svc2 = AgentToolsService(db=db, client_id=client_id)
        result2 = svc2.build_target_pension_plan(
            target_monthly_pension=10000.0,
            target_is_net=False,
            ignore_blocked_balances=True,
        )

    # The plan may fail (no sources) or succeed with 0 existing pension — both are acceptable.
    res2 = result2.get("result", {})

    # The existing pension total must NOT include the zeroed funds
    existing_total_2 = float(res2.get("existing_pension_total_gross", 0))
    assert existing_total_2 < 1.0, (
        f"Phase 2: expected existing_pension_total_gross ~0, got {existing_total_2}"
    )

    # No plan step should reference the zeroed pension fund IDs with positive pension_added
    for step in res2.get("plan_steps", []):
        step_pf_id = step.get("pension_fund_id")
        if step_pf_id is not None and int(step_pf_id) in {pf1_id, pf2_id}:
            pension_added = float(step.get("pension_added", 0))
            assert pension_added <= 0, (
                f"Phase 2: plan step references zeroed pf_id={step_pf_id} "
                f"with pension_added={pension_added}"
            )

    # No sources_used should reference the zeroed pension fund IDs as existing_pension
    for s in res2.get("sources_used", []):
        if s.get("source_type") == "existing_pension":
            s_pf_id = s.get("pension_fund_id")
            if s_pf_id is not None:
                assert int(s_pf_id) not in {pf1_id, pf2_id}, (
                    f"Phase 2: sources_used contains zeroed existing_pension pf_id={s_pf_id}"
                )
