import json

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def test_stream_pending_approval_replay_execute_scenario(monkeypatch) -> None:
    def fake_chat_stream(messages, client_id=None):
        raise AssertionError(
            "LLM must not be called for deterministic max-capital routing"
        )

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

    tool_calls: list[str] = []

    def fake_execute_tool_call(
        *,
        tool_name: str,
        args: dict,
        client_id: int,
        db,
        pension_portfolio=None,
        force_max_exemption: bool = False,
        agent_reply: str | None = None,
        user_approved: bool = False,
        request_id: str | None = None,
    ) -> str:
        tool_calls.append(tool_name)
        if tool_name == "RUN_RETIREMENT_SCENARIOS":
            return json.dumps(
                {
                    "retirement_age": 67,
                    "scenarios": [
                        {
                            "scenario_id": 123,
                            "scenario_key": "scenario_2_max_capital",
                            "scenario_name": "מקסימום הון (קצבת מינימום: 5,500)",
                        }
                    ],
                },
                ensure_ascii=False,
            )
        return json.dumps({"success": True}, ensure_ascii=False)

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)

    response1 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 777002,
            "messages": [{"role": "user", "content": "משיכה הונית מלאה - בצע"}],
            "pension_portfolio": [
                {
                    "מספר_חשבון": "494930",
                    "שם_תכנית": "עדיף",
                    "חברה_מנהלת": "",
                    "סוג_מוצר": "פוליסת ביטוח חיים משולב חיסכון",
                    "יתרה": 100000,
                }
            ],
        },
    )
    assert response1.status_code == 200
    body1 = response1.text
    assert "###UI_ACTION###" in body1
    assert "approval_request" in body1
    assert "EXECUTE_RETIREMENT_SCENARIO" in body1
    assert tool_calls == ["RUN_RETIREMENT_SCENARIOS"]

    response2 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 777002,
            "messages": [{"role": "user", "content": "משיכה הונית מלאה - בצע"}],
            "pension_portfolio": [
                {
                    "מספר_חשבון": "494930",
                    "שם_תכנית": "עדיף",
                    "חברה_מנהלת": "",
                    "סוג_מוצר": "פוליסת ביטוח חיים משולב חיסכון",
                    "יתרה": 100000,
                }
            ],
        },
    )
    assert response2.status_code == 200
    body2 = response2.text
    assert body2 == body1
    assert tool_calls == ["RUN_RETIREMENT_SCENARIOS"]
