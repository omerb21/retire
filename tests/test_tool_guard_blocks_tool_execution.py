import json

from app.models.client import Client
from app.schemas.llm_chat import ChatMessage, ChatRequest
from app.services.agent_execution.policy import ExecutionMode, PolicyDecision
from app.services.agent_execution.tool_execution_context import (
    set_tool_execution_context,
)
from app.services.agent_execution.tool_executor import execute_with_guard


def test_tool_guard_blocks_tool_execution_emits_validation_error(
    monkeypatch, _test_db
) -> None:
    Session = _test_db["Session"]

    # If underlying tool execution is called, fail.
    import app.services.llm_chat.tool_execution as tool_exec

    def _boom(*args, **kwargs):
        raise AssertionError(
            "Underlying execute_tool_call must NOT be called when guard blocks"
        )

    monkeypatch.setattr(tool_exec, "execute_tool_call", _boom)

    emitted = []

    def fake_log_trace_event(*, event_type, payload, client_id=None, endpoint=None):
        emitted.append(
            {
                "event_type": event_type,
                "payload": payload,
                "client_id": client_id,
                "endpoint": endpoint,
            }
        )

    import app.services.agent_execution.tool_executor as te

    monkeypatch.setattr(te, "log_trace_event", fake_log_trace_event)

    req = ChatRequest(
        messages=[ChatMessage(role="user", content="GET_CLIENT_SNAPSHOT")], client_id=1
    )
    decision = PolicyDecision(
        mode=ExecutionMode.LLM_TOOL_ROUTED, tools_allowed=False, write_allowed=False
    )

    with Session() as db:
        client = db.query(Client).filter(Client.id == 1).first()
        if client is None:
            client = Client(
                id=1, id_number_raw="1", id_number="1", full_name="Test User"
            )
            db.add(client)
            db.commit()

        set_tool_execution_context(
            request=req, policy_decision=decision, intent_type=None, streaming=False
        )

        res = execute_with_guard(
            request=req,
            db=db,
            tool_name="GET_CLIENT_SNAPSHOT",
            tool_args={},
            streaming=False,
            policy_decision=decision,
            intent_type=None,
            pension_portfolio=None,
            force_max_exemption=False,
            agent_reply=None,
            user_approved=True,
            request_id=None,
        )

    assert isinstance(res, dict)
    assert res.get("status") == "policy_blocked"

    validation_events = [e for e in emitted if e["event_type"] == "validation_error"]
    assert validation_events, f"Expected validation_error trace event, got {emitted}"
    assert validation_events[0]["payload"].get("tool_name") == "GET_CLIENT_SNAPSHOT"
