import json
from datetime import date

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
import app.services.llm_chat.chat_stream_orchestration_parts.orchestrator_impl_parts.stream_loop as stream_loop
import app.services.llm_chat.chat_stream_orchestration_parts.stream_system_prompt_generators as stream_gens
from app.main import app
from app.models.client import Client


def test_stream_target_plan_injects_retirement_age_75(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]

    with Session() as db:
        client = db.query(Client).filter(Client.id == 920000011).first()
        if client is None:
            client = Client(
                id=920000011,
                id_number_raw="920000011",
                id_number="920000011",
                full_name="Test User",
                birth_date=date(1953, 4, 16),
                gender="male",
            )
            db.add(client)
            db.flush()
        client_id = int(getattr(client, "id", 0) or 0)
        db.commit()

    def fake_today() -> date:
        return date(2026, 1, 27)

    monkeypatch.setattr(stream_loop, "_today", fake_today)
    monkeypatch.setattr(stream_gens, "_today", fake_today)

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError(
            "LLM must not be called for deterministic target plan routing"
        )

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

    seen_args: list[dict] = []

    def fake_execute_tool_call(
        *, tool_name: str, args: dict, client_id: int, db, **kwargs
    ) -> str:
        assert tool_name == "BUILD_TARGET_PENSION_PLAN"
        seen_args.append(args)
        assert int(args.get("retirement_age")) == 75
        assert "67" not in json.dumps(args, ensure_ascii=False)
        return "תכנית משיכה – סיכום:\n- גיל 75"

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    def fake_load_latest_pension_portfolio_snapshot_models(db, client_id):
        return None

    monkeypatch.setattr(
        stream_orch,
        "load_latest_pension_portfolio_snapshot_models",
        fake_load_latest_pension_portfolio_snapshot_models,
    )

    api = TestClient(app)
    resp = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [
                {
                    "role": "user",
                    "content": "עוד 3 שנים, בנה תכנית משיכה לגיל 75. יעד נטו: 33000",
                }
            ],
            "pension_portfolio": [],
        },
    )

    assert resp.status_code == 200
    assert seen_args
    assert "75" in resp.text
    assert "67" not in resp.text
