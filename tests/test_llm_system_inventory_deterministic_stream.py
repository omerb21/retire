import json

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def test_stream_system_inventory_bypasses_llm_and_uses_snapshot_tool(
    monkeypatch,
) -> None:
    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM should not be called for system inventory requests")

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
    ) -> str:
        tool_calls.append((tool_name, args))
        assert tool_name == "GET_SYSTEM_STATE_SNAPSHOT"
        return json.dumps(
            {
                "client_id": client_id,
                "generated_at": "2026-01-01T12:00:00Z",
                "counts": {
                    "pension_funds": 2,
                    "capital_assets": 3,
                    "additional_incomes": 1,
                    "current_employers": 1,
                    "employer_grants": 2,
                    "legacy_grants": 1,
                    "termination_events": 1,
                    "fixation_results": 1,
                    "pensions": 0,
                    "commutations": 0,
                    "scenarios": 4,
                },
                "entities": {
                    "pension_funds": [{"fund_name": "קרן פנסיה 1"}],
                    "capital_assets": [{"asset_name": "נכס הון 1"}],
                    "current_employers": [{"employer_name": "מעסיק"}],
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
            "messages": [{"role": "user", "content": "תציג לי מה יש בפועל במערכת"}],
        },
    )

    assert response.status_code == 200
    body = response.text
    assert "מצב בפועל במערכת" in body
    assert "סיכום ישויות" in body
    assert "קצבאות (PensionFund): 2" in body
    assert tool_calls and tool_calls[0][0] == "GET_SYSTEM_STATE_SNAPSHOT"


def test_stream_list_all_entities_bypasses_llm_and_formats(monkeypatch) -> None:
    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM should not be called for list-all-entities requests")

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

    def fake_execute_tool_call(
        *,
        tool_name: str,
        args: dict,
        client_id: int,
        db,
        pension_portfolio=None,
        force_max_exemption: bool = False,
    ) -> str:
        assert tool_name == "GET_SYSTEM_STATE_SNAPSHOT"
        return json.dumps(
            {
                "client_id": client_id,
                "generated_at": "2026-01-01T12:00:00Z",
                "counts": {
                    "pension_funds": 0,
                    "capital_assets": 0,
                    "additional_incomes": 1,
                },
                "entities": {
                    "additional_incomes": [
                        {
                            "id": 1,
                            "client_id": client_id,
                            "source_type": "business",
                            "description": "עסק",
                            "amount": 12000,
                            "frequency": "monthly",
                            "start_date": "2025-01-01",
                            "end_date": None,
                            "tax_treatment": "taxable",
                        }
                    ],
                    "pension_funds": [],
                    "capital_assets": [],
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
            "messages": [
                {
                    "role": "user",
                    "content": "תציג לי את כל ההכנסות, הקצבאות ונכסי הון שיש לי",
                }
            ],
            "pension_portfolio": [],
        },
    )

    assert response.status_code == 200
    body = response.text
    assert "הכנסות נוספות" in body
    assert "קצבאות" in body
    assert "נכסי הון" in body
    assert "עסק" in body
