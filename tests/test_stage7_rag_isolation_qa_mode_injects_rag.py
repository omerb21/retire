from app.schemas.llm_chat import ChatMessage, ChatRequest
from app.services.llm_chat.message_preparation import prepare_messages_with_context

from app.services.agent_execution.policy import ExecutionMode, PolicyDecision
from app.services.agent_execution.tool_execution_context import set_tool_execution_context


def test_stage7_qa_mode_injects_rag_and_keeps_order(monkeypatch, db_session, client) -> None:
    sentinel = "__SENTINEL_RAG__"

    calls = {"n": 0}

    def fake_build_rag_system_message(*, user_message: str):
        calls["n"] += 1
        return (
            "ידע מערכת שנשלף מה-Knowledge Base (חובה להשתמש בו):\n"
            + sentinel
        )

    monkeypatch.setattr(
        "app.services.llm_chat.message_preparation.build_rag_system_message",
        fake_build_rag_system_message,
    )

    req = ChatRequest(
        client_id=client.id,
        messages=[ChatMessage(role="user", content="איך מבצעים פריסת מס?")],
        pension_portfolio=None,
    )

    # QA mode = tools_allowed=False
    set_tool_execution_context(
        request=req,
        policy_decision=PolicyDecision(
            mode=ExecutionMode.LLM_TOOL_ROUTED,
            tools_allowed=False,
            write_allowed=False,
            missing_params=[],
        ),
        intent_type=None,
        streaming=False,
    )

    messages, _computed = prepare_messages_with_context(req, db_session)

    assert calls["n"] == 1

    system_contents = [m.content or "" for m in messages if getattr(m, "role", None) == "system"]

    rag_positions = [
        i
        for i, c in enumerate(system_contents)
        if c.lstrip().startswith("ידע מערכת שנשלף מה-Knowledge Base") and sentinel in c
    ]
    assert len(rag_positions) == 1

    global_prompt_positions = [i for i, c in enumerate(system_contents) if "אתה יועץ פרישה פנסיוני דיגיטלי" in c]
    assert global_prompt_positions

    # Ordering invariant: when QA injects RAG, global system prompt comes after it.
    assert rag_positions[0] < global_prompt_positions[0]
