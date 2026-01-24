import json
from datetime import date

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
import app.services.llm_chat.chat_stream_orchestration_parts.orchestrator_impl_parts.stream_loop as stream_loop
from app.main import app
from app.models.client import Client


def test_stream_build_target_plan_then_execute_requests_approval(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]

    with Session() as db:
        client = db.query(Client).filter(Client.id == 950000001).first()
        if client is None:
            client = Client(
                id=950000001,
                id_number_raw="950000001",
                id_number="950000001",
                full_name="Test User",
                birth_date=date(1980, 1, 1),
            )
            db.add(client)
            db.flush()
        client_id = int(getattr(client, "id", 0) or 0)
        db.commit()

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for deterministic build/execute target plan")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    def fake_build_transform_accounts_from_target_plan_payload(payload: dict):
        return [
            {
                "account_number": "A-001",
                "specific_amounts": {"תגמולי_עובד_אחרי_2000": 1000},
            }
        ]

    monkeypatch.setattr(
        stream_orch,
        "build_transform_accounts_from_target_plan_payload",
        fake_build_transform_accounts_from_target_plan_payload,
    )

    tool_calls: list[tuple[str, dict]] = []

    def fake_execute_tool_call(tool_name: str, args: dict, client_id: int, db, **kwargs) -> str:
        tool_calls.append((tool_name, args))
        assert tool_name != "RUN_RETIREMENT_CASHFLOW_ANALYSIS"
        assert tool_name == "BUILD_TARGET_PENSION_PLAN"
        payload = {
            "tool_name": "BUILD_TARGET_PENSION_PLAN",
            "args": args,
            "result": {"sources_used": []},
        }
        return (
            "OK\n\n###TARGET_PENSION_PLAN_DATA###\n"
            + json.dumps(payload, ensure_ascii=False)
            + "\n###END_TARGET_PENSION_PLAN_DATA###"
        )

    monkeypatch.setattr(stream_loop, "_execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)

    resp1 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "חשב תכנית קצבה של 31000 נטו"}],
            "pension_portfolio": [],
        },
    )
    assert resp1.status_code == 200
    assert tool_calls and tool_calls[0][0] == "BUILD_TARGET_PENSION_PLAN"

    resp2 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "בצע את התכנית בפועל"}],
            "pension_portfolio": [],
        },
    )
    assert resp2.status_code == 200
    assert "###UI_ACTION###" in resp2.text
    assert "TRANSFORM_FUNDS_TO_ASSETS" in resp2.text
    assert "כתוב: יעד נטו" not in resp2.text
