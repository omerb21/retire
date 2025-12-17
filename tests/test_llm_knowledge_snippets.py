from app.schemas.llm_chat import ChatMessage, ChatRequest
from app.services.llm_chat.message_preparation import prepare_messages_with_context


def test_prepare_messages_injects_knowledge_snippet_when_relevant(db_session, client) -> None:
    req = ChatRequest(
        client_id=client.id,
        messages=[
            ChatMessage(
                role="user",
                content="הסבר לי בבקשה על פריסת מס (tax spread) ואיך זה מוצג בתזרים.",
            )
        ],
        pension_portfolio=None,
    )

    messages, _computed = prepare_messages_with_context(req, db_session)
    system_contents = [m.content for m in messages if m.role == "system"]

    assert any("ידע מערכת רלוונטי" in c for c in system_contents)
    assert any("TAX_SPREAD_LOGIC.md" in c for c in system_contents)


def test_prepare_messages_does_not_inject_knowledge_when_irrelevant(db_session, client) -> None:
    req = ChatRequest(
        client_id=client.id,
        messages=[ChatMessage(role="user", content="מה שלומך?")],
        pension_portfolio=None,
    )

    messages, _computed = prepare_messages_with_context(req, db_session)
    system_contents = [m.content for m in messages if m.role == "system"]

    assert not any("ידע מערכת רלוונטי" in c for c in system_contents)
