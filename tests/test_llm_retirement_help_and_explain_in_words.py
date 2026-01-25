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
    tool_calls: list[str] = []

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for deterministic cashflow/explain paths")

    def fake_execute_tool_call(*, tool_name: str, args: dict, client_id: int, db, **kwargs) -> str:
        tool_calls.append(tool_name)
        if tool_name != "RUN_RETIREMENT_CASHFLOW_ANALYSIS":
            raise AssertionError("Unexpected tool call")
        return json.dumps(
            {
                "success": True,
                "tool_name": "RUN_RETIREMENT_CASHFLOW_ANALYSIS",
                "result": {
                    "monthly_deficit_or_surplus": 1.0,
                    "desired_income_is_net": True,
                    "is_sustainable": True,
                },
                "explanation": "TOOL_OUTPUT",
            },
            ensure_ascii=False,
        )

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
                    "content": "יעד נטו: 40000. תחשב לי תזרים פרישה",
                }
            ],
            "pension_portfolio": [],
        },
    )
    assert resp1.status_code == 200
    assert tool_calls == ["RUN_RETIREMENT_CASHFLOW_ANALYSIS"]

    def no_tool_call_after(*args, **kwargs):
        raise AssertionError("No tools should be executed for explain-in-words")

    monkeypatch.setattr(stream_orch, "execute_tool_call", no_tool_call_after)

    resp2 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [
                {"role": "user", "content": "יעד נטו: 40000. תחשב לי תזרים פרישה"},
                {"role": "assistant", "content": resp1.text},
                {"role": "user", "content": "הסבר במילים"},
            ],
            "pension_portfolio": [],
        },
    )

    assert resp2.status_code == 200
    body = resp2.text
    assert re.search(r"\d", body) is None
    assert ("עודף" in body) or ("גירעון" in body)
    assert "צעד הבא" in body


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
