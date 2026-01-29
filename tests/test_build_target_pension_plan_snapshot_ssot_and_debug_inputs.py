import json
from datetime import date, datetime, timezone
from uuid import uuid4

import pytest

from app.models.client import Client
from app.models.scenario import Scenario
from app.services.llm_agent_tools_service import AgentToolsService


def test_build_target_plan_uses_only_pension_portfolio_snapshot_and_skips_transform_meta(db_session) -> None:
    unique_id = f"ssot-{uuid4()}"
    client_obj = Client(
        id_number_raw=unique_id,
        id_number=unique_id,
        full_name="SSOT Test",
        birth_date=date(1980, 1, 1),
        gender="male",
        is_active=True,
        current_employer_exists=False,
    )
    db_session.add(client_obj)
    db_session.commit()
    db_session.refresh(client_obj)

    client_id = client_obj.id

    non_transform_portfolio = [
        {
            "מספר_חשבון": "A1",
            "שם_תכנית": "Fund A",
            "סוג_מוצר": "קופת גמל",
            "יתרה": 100000,
            "תאריך_התחלה": "2005-01-01",
            "תגמולי_עובד_אחרי_2000": 100000,
        },
        {
            "מספר_חשבון": "A2",
            "שם_תכנית": "Fund B",
            "סוג_מוצר": "קופת גמל",
            "יתרה": 200000,
            "תאריך_התחלה": "2006-01-01",
            "תגמולי_עובד_אחרי_2000": 200000,
        },
    ]

    transform_portfolio = [
        {
            "מספר_חשבון": "T1",
            "שם_תכנית": "Transformed",
            "סוג_מוצר": "קופת גמל",
            "יתרה": 999999,
            "תאריך_התחלה": "2001-01-01",
            "תגמולי": 999999,
        }
    ]

    undo_portfolio = [
        {
            "מספר_חשבון": "U1",
            "שם_תכנית": "Undo",
            "סוג_מוצר": "קופת גמל",
            "יתרה": 888888,
            "תאריך_התחלה": "2001-01-01",
            "תגמולי": 888888,
        }
    ]

    db_session.add(
        Scenario(
            client_id=client_id,
            scenario_name="undo_snapshot",
            apply_tax_planning=False,
            apply_capitalization=False,
            apply_exemption_shield=False,
            parameters=json.dumps({"pension_portfolio": undo_portfolio}, ensure_ascii=False),
            created_at=datetime(2025, 3, 1, tzinfo=timezone.utc),
        )
    )

    db_session.add(
        Scenario(
            client_id=client_id,
            scenario_name="pension_portfolio_snapshot",
            apply_tax_planning=False,
            apply_capitalization=False,
            apply_exemption_shield=False,
            parameters=json.dumps({"pension_portfolio": non_transform_portfolio}, ensure_ascii=False),
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
    )

    db_session.add(
        Scenario(
            client_id=client_id,
            scenario_name="pension_portfolio_snapshot",
            apply_tax_planning=False,
            apply_capitalization=False,
            apply_exemption_shield=False,
            parameters=json.dumps(
                {
                    "pension_portfolio": transform_portfolio,
                    "_meta": {"operation_type": "TRANSFORM_FUNDS_TO_ASSETS", "trace_id": "T"},
                },
                ensure_ascii=False,
            ),
            created_at=datetime(2025, 2, 1, tzinfo=timezone.utc),
        )
    )

    db_session.commit()

    svc = AgentToolsService(db_session, client_id, client_object=client_obj)

    res = svc.build_target_pension_plan(
        target_monthly_pension=1000,
        retirement_age=67,
        target_is_net=False,
        ignore_blocked_balances=True,
    )
    assert res.get("success") is True, res
    plan_res = res.get("result") if isinstance(res.get("result"), dict) else {}
    dbg = plan_res.get("debug_inputs") if isinstance(plan_res.get("debug_inputs"), dict) else {}

    assert int(dbg.get("portfolio_sources_count") or 0) == 2
    assert float(dbg.get("portfolio_total_balance") or 0) == pytest.approx(300000.0)
    assert float(dbg.get("blocked_total_detected") or 0) == pytest.approx(0.0)


def test_build_target_plan_debug_inputs_blocked_total_detected_and_coeff_diagnostics(db_session, monkeypatch) -> None:
    from app.services.llm_agent_tools.adapters import pension_sources as pension_sources_mod

    def _mock_coeff(*args, **kwargs):
        return {
            "factor_value": 200.0,
            "source_table": "default",
            "source_keys": {},
            "target_year": None,
            "guarantee_months": None,
            "notes": "test",
        }

    monkeypatch.setattr(pension_sources_mod, "get_annuity_coefficient", _mock_coeff)

    unique_id = f"diag-{uuid4()}"
    client_obj = Client(
        id_number_raw=unique_id,
        id_number=unique_id,
        full_name="Diag Test",
        birth_date=date(1980, 1, 1),
        gender="male",
        is_active=True,
        current_employer_exists=False,
    )
    db_session.add(client_obj)
    db_session.commit()
    db_session.refresh(client_obj)

    client_id = client_obj.id

    portfolio = [
        {
            "מספר_חשבון": "A1",
            "שם_תכנית": "Plan A",
            "סוג_מוצר": "קופת גמל",
            "יתרה": 150000,
            "תאריך_התחלה": "2005-01-01",
            "תגמולי_עובד_אחרי_2000": 100000,
            "פיצויים_שלא_עברו_התחשבנות": 50000,
        }
    ]

    db_session.add(
        Scenario(
            client_id=client_id,
            scenario_name="pension_portfolio_snapshot",
            apply_tax_planning=False,
            apply_capitalization=False,
            apply_exemption_shield=False,
            parameters=json.dumps({"pension_portfolio": portfolio}, ensure_ascii=False),
            created_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()

    svc = AgentToolsService(db_session, client_id, client_object=client_obj)

    res = svc.build_target_pension_plan(
        target_monthly_pension=300,
        retirement_age=67,
        target_is_net=False,
        ignore_blocked_balances=True,
    )
    assert res.get("success") is True, res
    plan_res = res.get("result") if isinstance(res.get("result"), dict) else {}
    dbg = plan_res.get("debug_inputs") if isinstance(plan_res.get("debug_inputs"), dict) else {}

    assert float(dbg.get("blocked_total_detected") or 0) == pytest.approx(50000.0)

    used = dbg.get("sources_used")
    assert isinstance(used, list) and used
    row = used[0]
    assert "coeff_source_table" in row
    assert "fallback_used" in row
    assert row.get("coeff_source_table") == "default"
    assert row.get("fallback_used") is True


def test_portfolio_source_fallback_used_false_when_non_default_coefficient(monkeypatch, client) -> None:
    from app.services.llm_agent_tools.adapters import pension_sources as pension_sources_mod

    def _mock_coeff(*args, **kwargs):
        return {
            "factor_value": 170.0,
            "source_table": "policy_generation_coefficient",
            "source_keys": {"generation_code": "X", "age": 67, "sex": "זכר"},
            "target_year": None,
            "guarantee_months": None,
            "notes": "test",
        }

    monkeypatch.setattr(pension_sources_mod, "get_annuity_coefficient", _mock_coeff)

    db = client._sa_instance_state.session
    svc = AgentToolsService(db, client.id, client_object=client)

    sources = svc._build_sources_from_pension_portfolio(
        pension_portfolio=[
            {
                "מספר_חשבון": "A1",
                "שם_תכנית": "Policy Like",
                "סוג_מוצר": "ביטוח מנהלים",
                "יתרה": 170000,
                "תאריך_התחלה": "2005-01-01",
                "תגמולי_עובד_אחרי_2000": 170000,
            }
        ],
        client=client,
        retirement_age=67,
        retirement_date=date(2047, 1, 1),
        retirement_year=2047,
    )

    assert isinstance(sources, list) and sources
    first = sources[0]
    assert first.get("coeff_source_table") == "policy_generation_coefficient"
    assert first.get("fallback_used") is False
