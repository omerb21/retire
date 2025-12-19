import json

import app.services.llm_chat.tool_execution as tool_execution


def test_execute_tool_call_dispatches_retirement_scenario_tools(db_session, client, monkeypatch) -> None:
    def _stub_run(*, args, agent_tools) -> str:
        assert isinstance(args, dict)
        assert agent_tools is not None
        return json.dumps({"stub": True, "tool": "RUN_RETIREMENT_SCENARIOS"}, ensure_ascii=False)

    def _stub_select(*, args, agent_tools) -> str:
        assert "target_monthly_pension" in args
        assert agent_tools is not None
        return json.dumps({"stub": True, "tool": "SELECT_TARGET_PENSION_SCENARIO"}, ensure_ascii=False)

    def _stub_find(*, args, agent_tools) -> str:
        assert "target_monthly_pension" in args
        assert agent_tools is not None
        return json.dumps({"stub": True, "tool": "FIND_OPTIMAL_SCENARIO"}, ensure_ascii=False)

    def _stub_execute(*, args, client_id: int, db) -> str:
        assert "scenario_id" in args
        assert client_id == client.id
        assert db is db_session
        return json.dumps({"stub": True, "tool": "EXECUTE_RETIREMENT_SCENARIO"}, ensure_ascii=False)

    monkeypatch.setattr(tool_execution, "handle_run_retirement_scenarios", _stub_run)
    monkeypatch.setattr(tool_execution, "handle_select_target_pension_scenario", _stub_select)
    monkeypatch.setattr(tool_execution, "handle_find_optimal_scenario", _stub_find)
    monkeypatch.setattr(tool_execution, "handle_execute_retirement_scenario", _stub_execute)

    out_run = tool_execution.execute_tool_call(
        tool_name="RUN_RETIREMENT_SCENARIOS",
        args={"retirement_age": 67},
        client_id=client.id,
        db=db_session,
        pension_portfolio=None,
        force_max_exemption=False,
    )
    assert json.loads(out_run)["tool"] == "RUN_RETIREMENT_SCENARIOS"

    out_select = tool_execution.execute_tool_call(
        tool_name="SELECT_TARGET_PENSION_SCENARIO",
        args={"target_monthly_pension": 10000},
        client_id=client.id,
        db=db_session,
        pension_portfolio=None,
        force_max_exemption=False,
    )
    assert json.loads(out_select)["tool"] == "SELECT_TARGET_PENSION_SCENARIO"

    out_find = tool_execution.execute_tool_call(
        tool_name="FIND_OPTIMAL_SCENARIO",
        args={"target_monthly_pension": 10000},
        client_id=client.id,
        db=db_session,
        pension_portfolio=None,
        force_max_exemption=False,
    )
    assert json.loads(out_find)["tool"] == "FIND_OPTIMAL_SCENARIO"

    out_execute = tool_execution.execute_tool_call(
        tool_name="EXECUTE_RETIREMENT_SCENARIO",
        args={"scenario_id": 123},
        client_id=client.id,
        db=db_session,
        pension_portfolio=None,
        force_max_exemption=False,
    )
    assert json.loads(out_execute)["tool"] == "EXECUTE_RETIREMENT_SCENARIO"
