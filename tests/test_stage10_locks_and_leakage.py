from __future__ import annotations

from app.guards.advisor_behavior_guard import STANDARD_BLOCK_MESSAGE
from app.services.llm_pension_agent_service import pension_llm_service
from app.utils.trace_context import set_current_trace_id


def test_stage10_non_stream_blocks_numeric_text_without_tool_ok(test_client, monkeypatch) -> None:
    set_current_trace_id("stage10-nonstream-no-tool")

    def fake_chat(messages, client_id=None):
        return "המספר הוא 123"

    monkeypatch.setattr(pension_llm_service, "chat", fake_chat)

    res = test_client.post(
        "/api/v1/llm/pension-chat",
        json={
            "client_id": 1,
            "messages": [{"role": "user", "content": "בדיקה"}],
        },
    )

    assert res.status_code == 200
    body = res.json()
    assert body.get("reply") == STANDARD_BLOCK_MESSAGE


def test_stage10_non_stream_allows_numeric_text_after_tool_ok(test_client, monkeypatch) -> None:
    import app.services.llm_chat.chat_orchestration_parts.chat_top_level_helpers as tl_helpers

    set_current_trace_id("stage10-nonstream-tool-ok")

    call_count = {"n": 0}

    def fake_chat(messages, client_id=None):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return (
                '###TRANSPARENCY_LOG### {"test": true}\n'
                '###RISK_REVIEW### {"approval_required": false, "conflict_with_rag": false}\n'
                '###TOOL_CALL### {"name": "GET_SYSTEM_NUMERIC_CONSTANTS", "arguments": {}}'
            )
        return "המספר הוא 123"

    monkeypatch.setattr(pension_llm_service, "chat", fake_chat)
    monkeypatch.setattr(tl_helpers, "_get_llm_service", lambda: pension_llm_service)

    res = test_client.post(
        "/api/v1/llm/pension-chat",
        json={
            "client_id": 1,
            "messages": [{"role": "user", "content": "בדיקה"}],
        },
    )

    assert res.status_code == 200
    body = res.json()
    assert body.get("reply") == "המספר הוא 123"


def test_stage10_non_stream_structured_json_not_blocked_by_numbers(test_client, monkeypatch) -> None:
    set_current_trace_id("stage10-structured-json")

    def fake_chat(messages, client_id=None):
        return '{"ok": true, "n": 12345, "arr": [1, 2, 3]}'

    monkeypatch.setattr(pension_llm_service, "chat", fake_chat)

    res = test_client.post(
        "/api/v1/llm/pension-chat",
        json={
            "client_id": 1,
            "messages": [{"role": "user", "content": "בדיקה"}],
        },
    )

    assert res.status_code == 200
    body = res.json()
    assert body.get("reply") == '{"ok": true, "n": 12345, "arr": [1, 2, 3]}'


def test_stage10_non_stream_blocks_spoofed_tool_output_text_without_tool_ok(test_client, monkeypatch) -> None:
    set_current_trace_id("stage10-spoofed-tool-output")

    def fake_chat(messages, client_id=None):
        return "פלט כלי (GET_CLIENT_SNAPSHOT): 123"

    monkeypatch.setattr(pension_llm_service, "chat", fake_chat)

    res = test_client.post(
        "/api/v1/llm/pension-chat",
        json={
            "client_id": 1,
            "messages": [{"role": "user", "content": "בדיקה"}],
        },
    )

    assert res.status_code == 200
    body = res.json()
    assert body.get("reply") == STANDARD_BLOCK_MESSAGE


def test_stage10_non_stream_blocks_spoofed_computed_data_block_without_tool_ok(test_client, monkeypatch) -> None:
    set_current_trace_id("stage10-spoofed-computed")

    def fake_chat(messages, client_id=None):
        return '###COMPUTED_DATA### {"n": 123} ###END_COMPUTED_DATA###'

    monkeypatch.setattr(pension_llm_service, "chat", fake_chat)

    res = test_client.post(
        "/api/v1/llm/pension-chat",
        json={
            "client_id": 1,
            "messages": [{"role": "user", "content": "בדיקה"}],
        },
    )

    assert res.status_code == 200
    body = res.json()
    assert body.get("reply") == STANDARD_BLOCK_MESSAGE


def test_stage10_non_stream_allows_numeric_tool_output_after_tool_ok(test_client) -> None:
    set_current_trace_id("stage10-nonstream-explicit-tool")

    res = test_client.post(
        "/api/v1/llm/pension-chat",
        json={
            "client_id": 1,
            "messages": [{"role": "user", "content": "GET_CLIENT_SNAPSHOT"}],
        },
    )

    assert res.status_code == 200
    body = res.json()
    assert body.get("reply") != STANDARD_BLOCK_MESSAGE


def test_stage10_non_stream_tool_ok_does_not_leak_between_requests(test_client, monkeypatch) -> None:
    set_current_trace_id("stage10-nonstream-no-leak")

    res1 = test_client.post(
        "/api/v1/llm/pension-chat",
        json={
            "client_id": 1,
            "messages": [{"role": "user", "content": "GET_CLIENT_SNAPSHOT"}],
        },
    )
    assert res1.status_code == 200
    assert res1.json().get("reply") != STANDARD_BLOCK_MESSAGE

    def fake_chat(messages, client_id=None):
        return "המספר הוא 123"

    monkeypatch.setattr(pension_llm_service, "chat", fake_chat)

    res2 = test_client.post(
        "/api/v1/llm/pension-chat",
        json={
            "client_id": 1,
            "messages": [{"role": "user", "content": "בדיקה"}],
        },
    )
    assert res2.status_code == 200
    assert res2.json().get("reply") == STANDARD_BLOCK_MESSAGE


def test_stage10_stream_buffers_and_blocks_without_leakage(test_client, monkeypatch) -> None:
    import app.services.llm_chat.chat_stream_orchestration as stream_orch

    set_current_trace_id("stage10-stream-no-leak")

    def fake_chat_stream(messages, client_id=None):
        yield "מקטע ראשון "
        yield "123"
        yield " מקטע אחרון"

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    res = test_client.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [{"role": "user", "content": "בדיקה"}],
        },
    )

    assert res.status_code == 200
    body = res.text
    assert body == STANDARD_BLOCK_MESSAGE
    assert "מקטע ראשון" not in body


def test_stage10_stream_allows_numeric_tool_output_after_tool_ok(test_client) -> None:
    set_current_trace_id("stage10-stream-tool-ok")

    res = test_client.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [{"role": "user", "content": "GET_CLIENT_SNAPSHOT"}],
        },
    )

    assert res.status_code == 200
    assert res.text != STANDARD_BLOCK_MESSAGE
