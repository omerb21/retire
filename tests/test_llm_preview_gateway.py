import json

import app.services.llm_chat.chat_orchestration as chat_orch
from app.schemas.llm_chat import ChatMessage, ChatRequest


def test_run_retirement_scenarios_preview_does_not_persist(db_session, client, monkeypatch) -> None:
    # LLM asks to run scenarios in preview mode
    responses = iter(
        [
            '###TRANSPARENCY_LOG### {"test": true}\n###RISK_REVIEW### {"approval_required": false, "conflict_with_rag": false}\n###TOOL_CALL### {"name": "RUN_RETIREMENT_SCENARIOS", "arguments": {"retirement_age": 67, "preview": true}}',
            "final",
        ]
    )

    def fake_chat(messages, client_id=None):
        return next(responses)

    monkeypatch.setattr(chat_orch.pension_llm_service, "chat", fake_chat)

    def fake_builder_build_all_scenarios(self):
        return {
            "scenario_1_max_pension": {"scenario_name": "S1", "total_pension_monthly": 1, "total_capital": 2, "estimated_npv": 3},
            "scenario_2_max_capital": {"scenario_name": "S2", "total_pension_monthly": 4, "total_capital": 5, "estimated_npv": 6},
        }

    from app.services.retirement import RetirementScenariosBuilder

    monkeypatch.setattr(RetirementScenariosBuilder, "build_all_scenarios", fake_builder_build_all_scenarios)

    # Capture DB commits to ensure none are done by preview
    commit_calls = {"n": 0}
    orig_commit = db_session.commit

    def counted_commit():
        commit_calls["n"] += 1
        return orig_commit()

    db_session.commit = counted_commit

    req = ChatRequest(
        messages=[ChatMessage(role="user", content="תן לי תרחישים לפרישה")],
        client_id=client.id,
        pension_portfolio=[],
    )

    _ = chat_orch.run_pension_chat(req, db_session)

    assert commit_calls["n"] == 0


def test_get_system_numeric_constants_returns_payload(db_session, client) -> None:
    tool_result = chat_orch.execute_tool_call(
        tool_name="GET_SYSTEM_NUMERIC_CONSTANTS",
        args={},
        client_id=client.id,
        db=db_session,
        pension_portfolio=[],
        force_max_exemption=False,
    )

    parsed = json.loads(tool_result)
    assert parsed.get("success") is True
    assert parsed.get("tool_name") == "GET_SYSTEM_NUMERIC_CONSTANTS"
    assert isinstance(parsed.get("result"), dict)
    assert "MINIMUM_PENSION" in parsed["result"]
