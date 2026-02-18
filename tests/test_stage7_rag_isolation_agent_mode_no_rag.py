from app.schemas.llm_chat import ChatMessage, ChatRequest
from app.services.llm_chat.message_preparation import prepare_messages_with_context

from app.services.agent_execution.policy import ExecutionMode, PolicyDecision
from app.services.agent_execution.tool_execution_context import set_tool_execution_context


def test_stage7_agent_mode_does_not_inject_rag_or_snippets(monkeypatch, db_session, client) -> None:
    sentinel = "__SENTINEL_RAG__"

    snippet_calls = {"n": 0}

    calls = {"n": 0}

    def fake_build_rag_system_message(*, user_message: str):
        calls["n"] += 1
        return sentinel

    def fake_build_knowledge_system_message(user_message: str):
        snippet_calls["n"] += 1
        return "__SENTINEL_SNIPPET__"

    monkeypatch.setattr(
        "app.services.llm_chat.message_preparation.build_rag_system_message",
        fake_build_rag_system_message,
    )

    monkeypatch.setattr(
        "app.services.llm_chat.message_preparation.build_knowledge_system_message",
        fake_build_knowledge_system_message,
    )

    req = ChatRequest(
        client_id=client.id,
        messages=[ChatMessage(role="user", content="איך מבצעים פריסת מס?")],
        pension_portfolio=None,
    )

    # Agent mode = tools_allowed=True
    set_tool_execution_context(
        request=req,
        policy_decision=PolicyDecision(
            mode=ExecutionMode.LLM_TOOL_ROUTED,
            tools_allowed=True,
            write_allowed=False,
            missing_params=[],
        ),
        intent_type=None,
        streaming=False,
    )

    messages, _computed = prepare_messages_with_context(req, db_session)

    assert calls["n"] == 0
    assert snippet_calls["n"] == 0

    system_contents = [m.content or "" for m in messages if getattr(m, "role", None) == "system"]
    assert not any(sentinel in c for c in system_contents)

    # Ensure the dedicated RAG/snippets blocks are not present at all.
    assert not any((c or "").lstrip().startswith("ידע מערכת שנשלף מה-Knowledge Base") for c in system_contents)
    assert not any((c or "").lstrip().startswith("ידע מערכת רלוונטי") for c in system_contents)
