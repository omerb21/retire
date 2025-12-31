from app.schemas.llm_chat import ChatMessage, ChatRequest
from app.services.llm_chat.message_preparation import prepare_messages_with_context


def test_prepare_messages_injects_rag_system_message_when_enabled(monkeypatch, db_session, client) -> None:
    def fake_build_rag_system_message(*, user_message: str):
        return "ידע מערכת שנשלף מה-Knowledge Base (חובה להשתמש בו):\n[1] MD/docs/example.md:1-10\nexample"

    monkeypatch.setattr(
        "app.services.llm_chat.message_preparation.build_rag_system_message",
        fake_build_rag_system_message,
    )

    req = ChatRequest(
        client_id=client.id,
        messages=[ChatMessage(role="user", content="איך מבצעים פריסת מס?")],
        pension_portfolio=None,
    )

    messages, _computed = prepare_messages_with_context(req, db_session)
    system_contents = [m.content for m in messages if m.role == "system"]

    assert any("ידע מערכת שנשלף מה-Knowledge Base" in c for c in system_contents)
