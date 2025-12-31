import app.services.llm_chat.chat_orchestration as chat_orchestration
from app.schemas.llm_chat import ChatMessage, ChatRequest
from app.services.llm_chat.chat_orchestration import run_pension_chat


def test_non_stream_blocks_build_target_plan_without_numeric_target(db_session, client, monkeypatch) -> None:
    responses = iter(
        [
            '###TOOL_CALL### {"name": "BUILD_TARGET_PENSION_PLAN", "arguments": {}}',
            "final answer",
        ]
    )

    def fake_chat(messages, client_id=None):
        return next(responses)

    monkeypatch.setattr(chat_orchestration.pension_llm_service, "chat", fake_chat)

    def fake_execute_tool_call(*args, **kwargs) -> str:
        raise AssertionError("execute_tool_call should not be invoked for invalid BUILD_TARGET_PENSION_PLAN calls")

    monkeypatch.setattr(chat_orchestration, "execute_tool_call", fake_execute_tool_call)

    req = ChatRequest(
        client_id=client.id,
        messages=[
            ChatMessage(
                role="user",
                content="אנא הצג אפשרויות משיכה מהתיק הפנסיוני והתעלם מהיתרות החסומות.",
            )
        ],
        pension_portfolio=None,
    )

    resp = run_pension_chat(req, db_session)
    assert "final answer" in (resp.reply or "")
    assert "###TOOL_CALL###" not in (resp.reply or "")
