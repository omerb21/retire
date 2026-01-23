import json
from datetime import date

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
import app.services.llm_chat.chat_stream_orchestration_parts.orchestrator_impl_parts.stream_loop as stream_loop
from app.main import app
from app.models.client import Client
from app.models.scenario import Scenario


def test_stream_text_approval_executes_pending_transform(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]

    with Session() as db:
        client = db.query(Client).filter(Client.id == 920000001).first()
        if client is None:
            client = Client(
                id=920000001,
                id_number_raw="920000001",
                id_number="920000001",
                full_name="Test User",
                birth_date=date(1980, 1, 1),
            )
            db.add(client)
            db.flush()
        client_id = int(getattr(client, "id", 0) or 0)

        tool_args = {
            "accounts": [{"account_id": "A", "amount": 1}],
            "use_provided_accounts_only": True,
            "ignore_blocked_balances": True,
            "skip_non_convertible_accounts": True,
        }
        pending = Scenario(
            client_id=client_id,
            scenario_name="pending_approval",
            apply_tax_planning=False,
            apply_capitalization=False,
            apply_exemption_shield=False,
            parameters=json.dumps(
                {"tool_name": "TRANSFORM_FUNDS_TO_ASSETS", "arguments": tool_args},
                ensure_ascii=False,
            ),
        )
        db.add(pending)
        db.commit()

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for text approval")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    tool_calls: list[tuple[str, dict]] = []

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
        tool_calls.append((tool_name, args))
        assert tool_name == "TRANSFORM_FUNDS_TO_ASSETS"
        assert user_approved is True
        return json.dumps({"success": True}, ensure_ascii=False)

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    resp = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "מאשר"}],
            "pension_portfolio": [],
        },
    )

    assert resp.status_code == 200
    assert tool_calls == [("TRANSFORM_FUNDS_TO_ASSETS", tool_args)]
    body = resp.text
    assert "🔧" in body
    assert "###USER_APPROVED###" not in body

    with Session() as db:
        pending_row = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "pending_approval")
            .first()
        )
        assert pending_row is None
