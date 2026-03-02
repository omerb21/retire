import asyncio
import json
from datetime import date

from app.models.client import Client
from app.schemas.llm_chat import ChatMessage, ChatRequest
from app.services.llm_chat.chat_stream_orchestration_parts.orchestrator_impl_parts import (
    stream_loop_user_approved_json_exec as user_approved_exec,
)
from app.services.llm_chat.guards.tool_execution_guard import GuardOutcome, GuardResult
from app.services.llm_chat.pending_approvals import store_pending_approval_ui_action


def test_stageE_guard_v2_blocks_prevents_tool_execution(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]

    client_id = 990000001
    stored_args = {
        "accounts": [{"account_id": "A", "amount": 1}],
        "use_provided_accounts_only": True,
    }

    with Session() as db:
        client = db.query(Client).filter(Client.id == client_id).first()
        if client is None:
            client = Client(
                id=client_id,
                id_number_raw=str(client_id),
                id_number=str(client_id),
                full_name="Test User",
                birth_date=date(1980, 1, 1),
            )
            db.add(client)
            db.flush()

        store_ok = store_pending_approval_ui_action(
            db=db,
            client_id=client_id,
            request_kind="execute_target_plan",
            tool_name="TRANSFORM_FUNDS_TO_ASSETS",
            tool_args=stored_args,
            ui_action="dummy",
        )
        assert store_ok is True
        db.commit()

    def fake_execute_tool_call(*args, **kwargs) -> str:
        raise AssertionError("Tool must not be executed when guard blocks")

    monkeypatch.setattr(
        user_approved_exec, "_execute_tool_call", fake_execute_tool_call
    )

    guard_calls: list[dict] = []

    def fake_guard_v2(
        *,
        tool_name: str,
        request_kind: str | None,
        has_pending_approval: bool,
        user_intent: str | None,
    ) -> GuardResult:
        guard_calls.append(
            {
                "tool_name": tool_name,
                "request_kind": request_kind,
                "has_pending_approval": has_pending_approval,
                "user_intent": user_intent,
            }
        )
        return GuardResult(outcome=GuardOutcome.BLOCK, error_code="TEST_BLOCK")

    monkeypatch.setattr(
        user_approved_exec, "evaluate_tool_execution_guard_v2", fake_guard_v2
    )

    payload = f"###USER_APPROVED### {json.dumps({'tool_name': 'TRANSFORM_FUNDS_TO_ASSETS', 'arguments': stored_args}, ensure_ascii=False)}"
    request = ChatRequest(
        client_id=client_id,
        messages=[ChatMessage(role="user", content=payload)],
        pension_portfolio=[],
    )
    with Session() as db:
        res = user_approved_exec._maybe_handle_user_approved_json_exec(
            request=request,
            db=db,
            stream_request_id="trace_stageE_default",
            original_user_msg=payload,
        )

    assert res is not None

    async def _collect_body() -> str:
        chunks: list[str] = []
        async for chunk in res.body_iterator:
            if isinstance(chunk, (bytes, bytearray)):
                chunks.append(chunk.decode("utf-8", errors="ignore"))
            else:
                chunks.append(str(chunk))
        return "".join(chunks)

    body = asyncio.run(_collect_body())
    assert "אין בקשת אישור פתוחה תואמת" in body
    assert "🔧" not in body
    assert "MCP_TOOL_EXEC_BLOCKED" not in body
    assert "BEHAVIOR_NOT_ACTIVATED" not in body

    assert guard_calls == [
        {
            "tool_name": "TRANSFORM_FUNDS_TO_ASSETS",
            "request_kind": "execute_target_plan",
            "has_pending_approval": True,
            "user_intent": "approve",
        }
    ]
