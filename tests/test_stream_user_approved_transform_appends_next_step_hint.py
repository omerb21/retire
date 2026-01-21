import json
from datetime import date

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app
from app.models.client import Client
from app.services.llm_chat.pending_approvals import store_pending_approval_ui_action


def test_user_approved_transform_appends_next_step_hint_only_on_success(
    monkeypatch, _test_db
) -> None:
    Session = _test_db["Session"]

    with Session() as db:
        client = db.query(Client).filter(Client.id == 900000003).first()
        if client is None:
            client = Client(
                id=900000003,
                id_number_raw="900000003",
                id_number="900000003",
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
        store_ok = store_pending_approval_ui_action(
            db=db,
            client_id=client_id,
            request_kind="execute_target_plan",
            tool_name="TRANSFORM_FUNDS_TO_ASSETS",
            tool_args=tool_args,
            ui_action="dummy",
        )
        assert store_ok is True
        db.commit()

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called when user approval marker is present")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    def fake_execute_tool_call_success(
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
        assert tool_name == "TRANSFORM_FUNDS_TO_ASSETS"
        assert user_approved is True
        return json.dumps({"success": True}, ensure_ascii=False)

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call_success)

    api = TestClient(app)
    response_ok = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [
                {
                    "role": "user",
                    "content": f"###USER_APPROVED### {json.dumps({'tool_name': 'TRANSFORM_FUNDS_TO_ASSETS', 'arguments': tool_args}, ensure_ascii=False)}",
                }
            ],
        },
    )

    assert response_ok.status_code == 200
    body_ok = response_ok.text
    assert "🔧" in body_ok
    assert "השלב הבא המומלץ: הפקת דוח" in body_ok
    assert body_ok.rfind("success") < body_ok.rfind("השלב הבא המומלץ: הפקת דוח")

    with Session() as db:
        store_ok2 = store_pending_approval_ui_action(
            db=db,
            client_id=client_id,
            request_kind="execute_target_plan",
            tool_name="TRANSFORM_FUNDS_TO_ASSETS",
            tool_args=tool_args,
            ui_action="dummy",
        )
        assert store_ok2 is True
        db.commit()

    def fake_execute_tool_call_fail(
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
        assert tool_name == "TRANSFORM_FUNDS_TO_ASSETS"
        assert user_approved is True
        return json.dumps({"success": False}, ensure_ascii=False)

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call_fail)

    response_fail = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [
                {
                    "role": "user",
                    "content": f"###USER_APPROVED### {json.dumps({'tool_name': 'TRANSFORM_FUNDS_TO_ASSETS', 'arguments': tool_args}, ensure_ascii=False)}",
                }
            ],
        },
    )

    assert response_fail.status_code == 200
    body_fail = response_fail.text
    assert "🔧" in body_fail
    assert "השלב הבא המומלץ: הפקת דוח" not in body_fail
