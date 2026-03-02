import json

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def test_stream_orchestration_plan_system_snapshot_uses_snapshot_tool_no_llm(
    monkeypatch,
) -> None:
    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for system snapshot orchestration")

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

    tool_calls: list[tuple[str, dict]] = []

    def fake_execute_tool_call(
        *,
        tool_name: str,
        args: dict,
        client_id: int,
        db,
        pension_portfolio=None,
        force_max_exemption: bool = False,
    ):
        tool_calls.append((tool_name, args))
        assert tool_name == "GET_SYSTEM_STATE_SNAPSHOT"
        return json.dumps(
            {
                "client_id": client_id,
                "generated_at": "2026-01-01T12:00:00Z",
                "counts": {
                    "pension_funds": 1,
                    "capital_assets": 0,
                    "additional_incomes": 0,
                    "current_employers": 0,
                    "employer_grants": 0,
                    "legacy_grants": 0,
                    "termination_events": 0,
                    "fixation_results": 0,
                    "pensions": 0,
                    "commutations": 0,
                    "scenarios": 0,
                },
                "entities": {
                    "pension_funds": [{"fund_name": "קרן"}],
                    "capital_assets": [],
                    "current_employers": [],
                },
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    def fake_load_latest_pension_portfolio_snapshot_models(db, client_id):
        return None

    monkeypatch.setattr(
        stream_orch,
        "load_latest_pension_portfolio_snapshot_models",
        fake_load_latest_pension_portfolio_snapshot_models,
    )

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [{"role": "user", "content": "מה יש במערכת"}],
        },
    )

    assert response.status_code == 200
    body = response.text

    assert tool_calls and len(tool_calls) == 1
    assert "מצב בפועל במערכת" in body
    assert "###UI_ACTION###" not in body
