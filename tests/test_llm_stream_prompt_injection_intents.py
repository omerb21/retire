from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
import app.services.llm_chat.chat_stream_orchestration_parts.orchestrator_impl_parts.stream_loop as stream_loop
from app.main import app


def test_stream_injects_base_prompt_and_playbook_into_llm_messages_no_tools(monkeypatch) -> None:
    captured = {"messages": None}

    monkeypatch.setattr(stream_loop, "_load_stream_intents_playbook_text", lambda: "PLAYBOOK_INTENTS_TEST")

    def fake_chat_stream(messages, client_id=None):
        captured["messages"] = messages
        yield "תשובה קצרה"

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [{"role": "user", "content": "אל תפעיל כלים. ענה רק במילים."}],
        },
    )

    assert response.status_code == 200
    assert captured["messages"] is not None

    system_contents = [m.content for m in captured["messages"] if getattr(m, "role", None) == "system"]
    assert any("/api/v1/llm/pension-chat-stream" in c for c in system_contents)
    assert any("NO_TOOLS" in c and "REPORT" in c and "ANALYSIS" in c for c in system_contents)
    assert any("PLAYBOOK_INTENTS_TEST" in c for c in system_contents)


    base_idx = next(i for i, c in enumerate(system_contents) if "/api/v1/llm/pension-chat-stream" in c)
    playbook_idx = next(i for i, c in enumerate(system_contents) if "PLAYBOOK_INTENTS_TEST" in c)
    intent_idx = next(i for i, c in enumerate(system_contents) if "מצב: NO_TOOLS" in c)
    assert base_idx < playbook_idx < intent_idx


def test_stream_injects_base_prompt_and_playbook_into_llm_messages_analysis(monkeypatch) -> None:
    captured = {"messages": None}

    monkeypatch.setattr(stream_loop, "_load_stream_intents_playbook_text", lambda: "PLAYBOOK_INTENTS_TEST")

    def fake_chat_stream(messages, client_id=None):
        captured["messages"] = messages
        yield '###TRANSPARENCY_LOG### {"t": true}\n###RISK_REVIEW### {"approval_required": false, "conflict_with_rag": false}\n###TOOL_CALL### {"name": "GET_PENSION_PRODUCTS", "arguments": {}}'

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    def fake_execute_tool_call(*args, **kwargs) -> str:
        return '{"success": true}'

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [{"role": "user", "content": "ניתוח ותיזמון פרישה"}],
        },
    )

    assert response.status_code == 200
    assert captured["messages"] is not None

    system_contents = [m.content for m in captured["messages"] if getattr(m, "role", None) == "system"]
    assert any("/api/v1/llm/pension-chat-stream" in c for c in system_contents)
    assert any("NO_TOOLS" in c and "REPORT" in c and "ANALYSIS" in c for c in system_contents)
    assert any("PLAYBOOK_INTENTS_TEST" in c for c in system_contents)

    base_idx = next(i for i, c in enumerate(system_contents) if "/api/v1/llm/pension-chat-stream" in c)
    playbook_idx = next(i for i, c in enumerate(system_contents) if "PLAYBOOK_INTENTS_TEST" in c)
    intent_idx = next(i for i, c in enumerate(system_contents) if "מצב: ANALYSIS" in c)
    assert base_idx < playbook_idx < intent_idx
