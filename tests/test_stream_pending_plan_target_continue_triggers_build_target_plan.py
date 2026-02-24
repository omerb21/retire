import json
from datetime import date

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
import app.services.llm_chat.chat_stream_orchestration_parts.orchestrator_impl_parts.stream_loop as stream_loop
from app.main import app
from app.models.client import Client


def test_stream_pending_plan_target_continue_triggers_build_target_plan(
    monkeypatch, _test_db
) -> None:
    Session = _test_db["Session"]

    with Session() as db:
        client = db.query(Client).filter(Client.id == 910000001).first()
        if client is None:
            client = Client(
                id=910000001,
                id_number_raw="910000001",
                id_number="910000001",
                full_name="Test User",
                birth_date=date(1980, 1, 1),
            )
            db.add(client)
            db.flush()
        client_id = int(getattr(client, "id", 0) or 0)
        db.commit()

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError(
            "LLM must not be called when pending_plan_target numeric continue triggers tools-first"
        )

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

    tool_calls: list[tuple[str, dict]] = []

    def fake_execute_tool_call(
        tool_name: str, args: dict, client_id: int, db, **kwargs
    ) -> str:
        try:
            from app.services.agent_execution.tool_execution_context import (
                mark_tool_ok_seen,
            )

            mark_tool_ok_seen()
        except Exception:
            pass
        tool_calls.append((tool_name, args))
        assert tool_name != "RUN_RETIREMENT_CASHFLOW_ANALYSIS"
        assert tool_name == "BUILD_TARGET_PENSION_PLAN"
        assert args.get("target_is_net") is True
        return json.dumps({"result": {"accumulated_pension": 0}}, ensure_ascii=False)

    monkeypatch.setattr(stream_loop, "_execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)

    resp1 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "בנה תכנית פרישה"}],
            "pension_portfolio": [],
        },
    )
    assert resp1.status_code == 200
    assert "כתוב: יעד נטו" in resp1.text

    resp2 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "יעד נטו: 31000"}],
            "pension_portfolio": [],
        },
    )
    assert resp2.status_code == 200
    assert tool_calls and tool_calls[0][0] == "BUILD_TARGET_PENSION_PLAN"
    assert "🔧" in resp2.text
