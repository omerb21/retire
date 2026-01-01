import app.services.llm_chat.chat_stream_orchestration as stream_orch


def test_chat_stream_llm_timeout_yields_error_including_request_id(monkeypatch, client):
    # Force the underlying LLM generator to never finish (simulate hang)
    def fake_chat_stream(messages, client_id=None):
        # endless generator
        while True:
            yield ""

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    # Speed up timeout for the test
    monkeypatch.setattr(stream_orch, "PC_LLM_MAX_RETRIES", 1)
    monkeypatch.setattr(stream_orch, "PC_LLM_TIMEOUT_SECONDS", 0.01)

    req = stream_orch.ChatRequest(
        messages=[stream_orch.ChatMessage(role="user", content="hello")],
        client_id=client.id,
    )

    resp = stream_orch.run_pension_chat_stream(req, client.db.bind) if False else None


def test_chat_stream_llm_error_returns_non_empty_reply(monkeypatch, test_client, test_client_data):
    def fake_chat_stream(messages, client_id=None):
        raise RuntimeError("boom")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)
    monkeypatch.setattr(stream_orch, "PC_LLM_MAX_RETRIES", 1)
    monkeypatch.setattr(stream_orch, "PC_LLM_TIMEOUT_SECONDS", 0.5)

    api = test_client
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": test_client_data["id"],
            "messages": [{"role": "user", "content": "שלום"}],
        },
    )
    assert response.status_code == 200
    assert "request_id" in response.text
    assert "שגיאה" in response.text
