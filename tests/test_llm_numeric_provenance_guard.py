import app.services.llm_chat.chat_orchestration as chat_orch
import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.guards.advisor_behavior_guard import STANDARD_BLOCK_MESSAGE
from app.schemas.llm_chat import ChatMessage, ChatRequest


def test_non_stream_blocks_unprovenanced_numbers(
    db_session, client, monkeypatch
) -> None:
    # LLM tries to output a number that was never provided by the user and never came from a tool
    def fake_chat(messages, client_id=None):
        return "המספר הוא 12345"

    monkeypatch.setattr(chat_orch.pension_llm_service, "chat", fake_chat)

    req = ChatRequest(
        client_id=client.id,
        messages=[ChatMessage(role="user", content="שלום")],
        pension_portfolio=[],
    )

    resp = chat_orch.run_pension_chat(req, db_session)
    assert "12345" in resp.reply


def test_non_stream_allows_user_provided_number(
    db_session, client, monkeypatch
) -> None:
    # If the user provided the number, the agent may repeat it (no calculation)
    def fake_chat(messages, client_id=None):
        return "כפי שכתבת: 28000"

    monkeypatch.setattr(chat_orch.pension_llm_service, "chat", fake_chat)

    req = ChatRequest(
        client_id=client.id,
        messages=[ChatMessage(role="user", content="היעד שלי הוא 28000")],
        pension_portfolio=[],
    )

    resp = chat_orch.run_pension_chat(req, db_session)
    assert "28000" in resp.reply


def test_stream_blocks_unprovenanced_numbers(
    monkeypatch, test_client, test_client_data
) -> None:
    def fake_chat_stream(messages, client_id=None):
        yield "המספר הוא 777"

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

    api = test_client
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": test_client_data["id"],
            "messages": [{"role": "user", "content": "שלום"}],
        },
    )
    assert response.status_code == 200
    assert response.text == STANDARD_BLOCK_MESSAGE
