import json

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
import app.services.llm_chat.tool_execution as tool_exec
from app.main import app
from app.models.client import Client
from app.services.llm_chat.pending_approvals import store_pending_approval_ui_action


def test_stream_user_approved_executes_tool_and_does_not_ask_again(
    monkeypatch, _test_db
) -> None:
    Session = _test_db["Session"]

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError(
            "LLM must not be called when user approval marker is present"
        )

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
        agent_reply: str | None = None,
        user_approved: bool = False,
        request_id: str | None = None,
    ) -> str:
        tool_calls.append((tool_name, args))
        assert tool_name == "TRANSFORM_FUNDS_TO_ASSETS"
        assert user_approved is True
        return json.dumps({"success": True}, ensure_ascii=False)

    monkeypatch.setattr(tool_exec, "execute_tool_call", fake_execute_tool_call)

    client_id = 1
    approved_args = {"accounts": [], "use_provided_accounts_only": True}
    with Session() as db:
        client = db.query(Client).filter(Client.id == client_id).first()
        if client is None:
            client = Client(
                id=client_id, id_number_raw="1", id_number="1", full_name="Test User"
            )
            db.add(client)
            db.flush()
        store_ok = store_pending_approval_ui_action(
            db=db,
            client_id=client_id,
            request_kind="execute_target_plan",
            tool_name="TRANSFORM_FUNDS_TO_ASSETS",
            tool_args=approved_args,
            ui_action="dummy",
        )
        assert store_ok is True
        db.commit()

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [
                {
                    "role": "user",
                    "content": f"###USER_APPROVED### {json.dumps({'tool_name': 'TRANSFORM_FUNDS_TO_ASSETS', 'arguments': approved_args}, ensure_ascii=False)}",
                }
            ],
        },
    )

    assert response.status_code == 200
    assert tool_calls == [("TRANSFORM_FUNDS_TO_ASSETS", approved_args)]

    body = response.text
    assert "נדרש אישור" not in body
    assert "###UI_ACTION###" not in body
    assert "🔧" in body
