from datetime import date

import pytest

from app.services.llm_agent_tools_service import AgentToolsService


def test_build_target_pension_plan_net_fails_if_tax_projection_unavailable(
    db_session, client
):
    # Create service with a real client, but monkeypatch its tax projection method.
    svc = AgentToolsService(db_session, client.id, client_object=client)

    def _raise_tax(*args, **kwargs):
        raise ValueError("TAX_TOOL_ERROR: simulated failure")

    svc.get_tax_projection = _raise_tax  # type: ignore

    res = svc.build_target_pension_plan(
        target_monthly_pension=28000, target_is_net=True
    )
    assert res.get("success") is False
    assert "לא ניתן לתכנן יעד קצבה נטו" in (res.get("explanation") or "")
    assert "TAX_TOOL_ERROR" in (res.get("explanation") or "")


@pytest.mark.parametrize("target_is_net", [True])
def test_build_target_pension_plan_net_does_not_silently_treat_net_as_gross(
    db_session, client, target_is_net
):
    svc = AgentToolsService(db_session, client.id, client_object=client)

    def _raise_tax(*args, **kwargs):
        raise ValueError("TAX_TOOL_ERROR: simulated failure")

    svc.get_tax_projection = _raise_tax  # type: ignore

    res = svc.build_target_pension_plan(
        target_monthly_pension=28000, target_is_net=target_is_net
    )
    assert res.get("success") is False
    # If it returned success, we'd be silently treating net like gross.
    assert res.get("result") == {}


def test_get_tax_projection_includes_db_additional_incomes(db_session, client):
    from app.models.additional_income import AdditionalIncome
    from datetime import date
    from decimal import Decimal

    svc = AgentToolsService(db_session, client.id, client_object=client)

    inc = AdditionalIncome(
        client_id=client.id,
        source_type="salary",
        description="side job",
        amount=Decimal("2000"),
        frequency="monthly",
        start_date=date.today(),
        end_date=None,
        indexation_method="none",
        tax_treatment="taxable",
        tax_rate=None,
    )
    db_session.add(inc)
    db_session.commit()

    res = svc.get_tax_projection(monthly_pension=20000)
    assert res.get("success") is True
    payload = res.get("result") or {}
    assert payload.get("portfolio_additional_income_monthly", 0) >= 2000
