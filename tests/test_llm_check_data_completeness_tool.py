import json

from app.services.llm_chat.tool_execution import execute_tool_call


def test_execute_tool_call_check_data_completeness_returns_json(
    db_session, client
) -> None:
    result = execute_tool_call(
        tool_name="CHECK_DATA_COMPLETENESS",
        args={},
        client_id=client.id,
        db=db_session,
        pension_portfolio=None,
        force_max_exemption=False,
    )

    assert isinstance(result, str)
    assert "Tool 'CHECK_DATA_COMPLETENESS' not found" not in result
    assert "Tool execution failed" not in result
    parsed = json.loads(result)
    assert "complete" in parsed
    assert "missing" in parsed
    assert "warnings" in parsed
    assert "recommendations" in parsed
