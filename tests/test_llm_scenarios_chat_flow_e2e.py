import json

import app.services.llm_chat.chat_orchestration as chat_orchestration
from app.schemas.llm_chat import ChatMessage, ChatRequest


def _build_sample_portfolio() -> list[dict]:
    return [
        {
            "מספר_חשבון": "A-001",
            "שם_תכנית": "קופת גמל כללית",
            "חברה_מנהלת": "חברה 1",
            "סוג_מוצר": "קופת גמל",
            "יתרה": 100000,
            "תאריך_התחלה": "2005-01-01",
        }
    ]


def test_llm_scenarios_chat_flow_runs_tools_then_summarizes(db_session, client, monkeypatch) -> None:
    calls: list[tuple[str, dict]] = []

    llm_replies = iter(
        [
            '###TOOL_CALL### {"name": "RUN_RETIREMENT_SCENARIOS", "arguments": {"retirement_age": 67}}',
            '###TOOL_CALL### {"name": "SELECT_TARGET_PENSION_SCENARIO", "arguments": {"target_monthly_pension": 12000}}',
            "סיכום תרחישים: בחרתי תרחיש שעומד ביעד הקצבה ומציג איזון טוב בין קצבה להון. האם לבצע בפועל?",
        ]
    )

    def fake_chat(messages, client_id=None):
        return next(llm_replies)

    monkeypatch.setattr(chat_orchestration.pension_llm_service, "chat", fake_chat)

    def fake_execute_tool_call(
        *,
        tool_name: str,
        args: dict,
        client_id: int,
        db,
        pension_portfolio=None,
        force_max_exemption: bool = False,
    ) -> str:
        calls.append((tool_name, args))

        if tool_name == "RUN_RETIREMENT_SCENARIOS":
            return json.dumps(
                {
                    "success": True,
                    "tool_name": tool_name,
                    "result": {
                        "retirement_age": args.get("retirement_age"),
                        "scenarios": [
                            {
                                "scenario_id": 1,
                                "scenario_type": "scenario_1_max_pension",
                                "total_pension_monthly": 13000,
                                "total_capital": 200000,
                                "estimated_npv": 1000000,
                            }
                        ],
                    },
                },
                ensure_ascii=False,
            )

        if tool_name == "SELECT_TARGET_PENSION_SCENARIO":
            return json.dumps(
                {
                    "success": True,
                    "tool_name": tool_name,
                    "result": {
                        "target_achieved": True,
                        "selected_scenario": {
                            "scenario_id": 1,
                            "scenario_type": "scenario_1_max_pension",
                            "total_pension_monthly": 13000,
                            "total_capital": 200000,
                            "estimated_npv": 1000000,
                        },
                    },
                },
                ensure_ascii=False,
            )

        raise AssertionError(f"Unexpected tool called in this test: {tool_name}")

    monkeypatch.setattr(chat_orchestration, "execute_tool_call", fake_execute_tool_call)

    req = ChatRequest(
        messages=[ChatMessage(role="user", content="תן לי 3 תרחישים לפרישה ובחר אחד שמתאים ליעד קצבה 12,000")],
        client_id=client.id,
        pension_portfolio=_build_sample_portfolio(),
    )

    resp = chat_orchestration.run_pension_chat(req, db_session)

    assert "###TOOL_CALL###" not in resp.reply
    assert "סיכום תרחישים" in resp.reply
    assert calls[0][0] == "RUN_RETIREMENT_SCENARIOS"
    assert calls[1][0] == "SELECT_TARGET_PENSION_SCENARIO"
