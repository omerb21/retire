from datetime import date

import pytest

from app.services.llm_agent_tools_service import AgentToolsService


def test_build_target_pension_plan_net_fails_if_tax_projection_unavailable(db_session, client):
    # Create service with a real client, but monkeypatch its tax projection method.
    svc = AgentToolsService(db_session, client.id, client_object=client)

    def _raise_tax(*args, **kwargs):
        raise ValueError("TAX_TOOL_ERROR: simulated failure")

    svc.get_tax_projection = _raise_tax  # type: ignore

    res = svc.build_target_pension_plan(target_monthly_pension=28000, target_is_net=True)
    assert res.get("success") is False
    assert "לא ניתן לתכנן יעד קצבה נטו" in (res.get("explanation") or "")
    assert "TAX_TOOL_ERROR" in (res.get("explanation") or "")


@pytest.mark.parametrize("target_is_net", [True])
def test_build_target_pension_plan_net_does_not_silently_treat_net_as_gross(db_session, client, target_is_net):
    svc = AgentToolsService(db_session, client.id, client_object=client)

    def _raise_tax(*args, **kwargs):
        raise ValueError("TAX_TOOL_ERROR: simulated failure")

    svc.get_tax_projection = _raise_tax  # type: ignore

    res = svc.build_target_pension_plan(target_monthly_pension=28000, target_is_net=target_is_net)
    assert res.get("success") is False
    # If it returned success, we'd be silently treating net like gross.
    assert res.get("result") == {}
