import json
from datetime import date

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
import app.services.llm_chat.chat_stream_orchestration_parts.orchestrator_impl_parts.stream_loop as stream_loop
from app.main import app
from app.models.client import Client


def test_stream_pending_retirement_age_followup_from_relative_years(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]

    with Session() as db:
        client = db.query(Client).filter(Client.id == 920000003).first()
        if client is None:
            client = Client(
                id=920000003,
                id_number_raw="920000003",
                id_number="920000003",
                full_name="Test User",
                birth_date=date(1953, 4, 16),
                gender="male",
            )
            db.add(client)
            db.flush()
        client_id = int(getattr(client, "id", 0) or 0)
        db.commit()

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError(
            "LLM must not be called for pending_plan_target continue flow; tools-first should run"
        )

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    def fake_today() -> date:
        return date(2026, 1, 27)

    monkeypatch.setattr(stream_loop, "_today", fake_today)

    tool_calls: list[tuple[str, dict]] = []

    def fake_execute_tool_call(tool_name: str, args: dict, client_id: int, db, **kwargs) -> str:
        tool_calls.append((tool_name, args))
        assert tool_name == "BUILD_TARGET_PENSION_PLAN"
        assert int(float(args.get("target_monthly_pension"))) == 33000
        assert args.get("target_is_net") is True
        assert int(args.get("retirement_age")) == 75
        assert "67" not in json.dumps(args, ensure_ascii=False)
        return "תכנית יעד קצבה – סיכום:\n- גיל פרישה בתכנון: 75"

    monkeypatch.setattr(stream_loop, "_execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)

    resp1 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [
                {
                    "role": "user",
                    "content": "אני רוצה לפרוש בעוד 3 שנים",
                }
            ],
            "pension_portfolio": [],
        },
    )
    assert resp1.status_code == 200
    assert "יעד" in resp1.text

    resp2 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "יעד נטו: 33000"}],
            "pension_portfolio": [],
        },
    )
    assert resp2.status_code == 200
    assert tool_calls and tool_calls[0][0] == "BUILD_TARGET_PENSION_PLAN"
    assert "75" in resp2.text
    assert "67" not in resp2.text
