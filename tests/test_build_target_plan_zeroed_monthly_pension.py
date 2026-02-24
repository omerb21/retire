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
    assert (
        res1["existing_pension_total_gross"] >= 5000.0
    ), f"Phase 1: expected existing_pension_total_gross >= 5000, got {res1['existing_pension_total_gross']}"

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

    # --- Phase 2: set pension_amount = 0 and record_status = draft for both ---
    with Session() as db:
        for pf_id in [pf1_id, pf2_id]:
            pf = db.query(PensionFund).filter(PensionFund.id == pf_id).first()
            assert pf is not None, f"PensionFund {pf_id} not found"
            pf.pension_amount = 0.0
            pf.record_status = "draft"
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
    assert (
        existing_total_2 < 1.0
    ), f"Phase 2: expected existing_pension_total_gross ~0, got {existing_total_2}"

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
                assert int(s_pf_id) not in {
                    pf1_id,
                    pf2_id,
                }, f"Phase 2: sources_used contains zeroed existing_pension pf_id={s_pf_id}"


def test_api_rejects_active_monthly_pension_with_zero_amount(_test_db) -> None:
    """Test A: creating an active monthly_pension with pension_amount=0 via API returns 400."""
    from fastapi.testclient import TestClient
    from app.main import app

    Session = _test_db["Session"]
    client_id = 970000002

    with Session() as db:
        client = db.query(Client).filter(Client.id == client_id).first()
        if client is None:
            client = Client(
                id=client_id,
                id_number_raw=str(client_id),
                id_number=str(client_id),
                full_name="Test API Validation",
                birth_date=date(1965, 3, 10),
                gender="female",
                is_active=True,
            )
            db.add(client)
            db.commit()

    test_client = TestClient(app)
    resp = test_client.post(
        f"/api/v1/clients/{client_id}/pension-funds",
        json={
            "client_id": client_id,
            "fund_name": "קצבה שלא צריכה להיווצר",
            "fund_type": "monthly_pension",
            "input_mode": "manual",
            "pension_amount": 0,
            "indexation_method": "none",
            "tax_treatment": "taxable",
        },
    )
    assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body.get("detail", {}).get("code") == "MONTHLY_PENSION_ZERO_AMOUNT"


def test_draft_monthly_pension_not_counted_in_plan(_test_db) -> None:
    """Test B: a monthly_pension with record_status=draft is not counted as existing pension."""
    Session = _test_db["Session"]
    client_id = 970000003

    with Session() as db:
        client = db.query(Client).filter(Client.id == client_id).first()
        if client is None:
            client = Client(
                id=client_id,
                id_number_raw=str(client_id),
                id_number=str(client_id),
                full_name="Test Draft Not Counted",
                birth_date=date(1960, 1, 1),
                gender="male",
                is_active=True,
            )
            db.add(client)
            db.flush()

        # Create a draft monthly_pension with pension_amount > 0
        pf_draft = PensionFund(
            client_id=client_id,
            fund_name="קצבה טיוטה",
            fund_type="monthly_pension",
            input_mode="manual",
            balance=0,
            pension_amount=5000.0,
            pension_start_date=date(2024, 1, 1),
            indexation_method="none",
            tax_treatment="taxable",
            record_status="draft",
        )
        db.add(pf_draft)

        ca = CapitalAsset(
            client_id=client_id,
            asset_name="נכס הון לבדיקת טיוטה",
            asset_type="savings",
            current_value=1_000_000.0,
            monthly_income=0,
            annual_return_rate=0.0,
            payment_frequency="monthly",
            start_date=date(2020, 1, 1),
            tax_treatment="taxable",
        )
        db.add(ca)
        db.commit()

    from app.services.llm_agent_tools_service import AgentToolsService

    with Session() as db:
        svc = AgentToolsService(db=db, client_id=client_id)
        result = svc.build_target_pension_plan(
            target_monthly_pension=10000.0,
            target_is_net=False,
            ignore_blocked_balances=True,
        )

    res = result.get("result", {})
    # The draft pension (5000) must NOT be counted as existing pension
    existing_total = float(res.get("existing_pension_total_gross", 0))
    assert (
        existing_total < 1.0
    ), f"Draft pension was counted: existing_pension_total_gross={existing_total}"


def test_maintenance_fix_zeroed_monthly_pensions(_test_db) -> None:
    """Test C: maintenance command demotes zeroed active monthly_pensions to draft."""
    Session = _test_db["Session"]
    client_id = 970000004

    with Session() as db:
        client = db.query(Client).filter(Client.id == client_id).first()
        if client is None:
            client = Client(
                id=client_id,
                id_number_raw=str(client_id),
                id_number=str(client_id),
                full_name="Test Maintenance Fix",
                birth_date=date(1958, 7, 20),
                gender="male",
                is_active=True,
            )
            db.add(client)
            db.flush()

        # Manually insert zeroed monthly_pension rows with record_status=active
        # (bypassing the model event listener by setting record_status explicitly after flush)
        pf_bad1 = PensionFund(
            client_id=client_id,
            fund_name="קצבה מאופסת 1",
            fund_type="monthly_pension",
            input_mode="manual",
            balance=0,
            pension_amount=0.0,
            pension_start_date=date(2024, 1, 1),
            indexation_method="none",
            tax_treatment="taxable",
            record_status="active",
        )
        pf_bad2 = PensionFund(
            client_id=client_id,
            fund_name="קצבה מאופסת 2",
            fund_type="monthly_pension",
            input_mode="manual",
            balance=0,
            pension_amount=None,
            pension_start_date=date(2024, 6, 1),
            indexation_method="none",
            tax_treatment="exempt",
            record_status="active",
        )
        # The model event listener will auto-demote these to draft on insert.
        # For the test to be meaningful, we verify the listener works.
        db.add(pf_bad1)
        db.add(pf_bad2)
        db.flush()

        bad1_id = pf_bad1.id
        bad2_id = pf_bad2.id

        # Verify the model event listener already demoted them
        assert (
            pf_bad1.record_status == "draft"
        ), "Event listener should have demoted pf_bad1"
        assert (
            pf_bad2.record_status == "draft"
        ), "Event listener should have demoted pf_bad2"

        # Force them back to active to test the maintenance command
        db.execute(
            PensionFund.__table__.update()
            .where(PensionFund.id.in_([bad1_id, bad2_id]))
            .values(record_status="active")
        )
        db.commit()

        # Verify they are active again
        pf_check1 = db.get(PensionFund, bad1_id)
        pf_check2 = db.get(PensionFund, bad2_id)
        db.refresh(pf_check1)
        db.refresh(pf_check2)
        assert pf_check1.record_status == "active"
        assert pf_check2.record_status == "active"

    # Run maintenance
    from app.services.pension_fund_maintenance import fix_zeroed_monthly_pensions

    with Session() as db:
        fix_result = fix_zeroed_monthly_pensions(db)
        db.commit()

    assert (
        fix_result["fixed_count"] >= 2
    ), f"Expected at least 2 fixed, got {fix_result}"
    assert bad1_id in fix_result["fixed_ids"]
    assert bad2_id in fix_result["fixed_ids"]

    # Verify they are now draft
    with Session() as db:
        pf_after1 = db.get(PensionFund, bad1_id)
        pf_after2 = db.get(PensionFund, bad2_id)
        assert (
            pf_after1.record_status == "draft"
        ), f"pf_bad1 still {pf_after1.record_status}"
        assert (
            pf_after2.record_status == "draft"
        ), f"pf_bad2 still {pf_after2.record_status}"
