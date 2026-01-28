import json
import re

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def test_general_retirement_help_does_not_run_tools(monkeypatch) -> None:
    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for general retirement help")

    def fake_execute_tool_call(*args, **kwargs):
        raise AssertionError("No tools should be executed for general retirement help")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)
    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [
                {
                    "role": "user",
                    "content": "אני בן 72 פרשתי לפני חודש. אני מבקש עזרה בתכנון הפרישה.",
                }
            ],
            "pension_portfolio": [],
        },
    )

    assert response.status_code == 200
    body = response.text

    assert "כותרת" in body
    assert "תכנון" in body
    assert "שאלות" in body
    assert re.search(r"\d", body) is None


def test_explain_in_words_after_cashflow_has_no_numbers_and_no_tools(monkeypatch) -> None:
    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for deterministic cashflow/explain paths")

    def fake_execute_tool_call(*args, **kwargs):
        raise AssertionError("No tools should be executed for cashflow without an existing plan")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)
    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)

    resp1 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [
                {
                    "role": "user",
                    "content": "יעד נטו: 40000. תחשב לי תזרים פרישה תאריך פרישה: 2030-01-01 גבר בן 67",
                }
            ],
            "pension_portfolio": [],
        },
    )
    assert resp1.status_code == 200
    assert resp1.text.strip() == "אין תכנית קיימת להצגת תזרים. יש לבנות תכנית תחילה."

    resp2 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [
                {
                    "role": "user",
                    "content": "יעד נטו: 40000. תחשב לי תזרים פרישה תאריך פרישה: 2030-01-01 גבר בן 67",
                },
                {"role": "assistant", "content": resp1.text},
                {"role": "user", "content": "הסבר במילים"},
            ],
            "pension_portfolio": [],
        },
    )

    assert resp2.status_code == 200
    body = resp2.text
    assert re.search(r"\d", body) is None
    assert "עקרונות" in body
    assert "כדי שאוכל להסביר" in body


def test_explain_in_words_without_prior_tool_is_general_and_no_numbers(monkeypatch) -> None:
    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for explain-in-words")

    def fake_execute_tool_call(*args, **kwargs):
        raise AssertionError("No tools should be executed for explain-in-words")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)
    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 9999,
            "messages": [{"role": "user", "content": "הסבר במילים"}],
            "pension_portfolio": [],
        },
    )

    assert response.status_code == 200
    body = response.text
    assert re.search(r"\d", body) is None
    assert "עקרונות" in body
    assert "מיפוי" in body
