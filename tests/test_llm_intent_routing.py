import json

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def test_stream_intent_no_tools_blocks_tool_call(monkeypatch) -> None:
    call_count = {"n": 0}

    def fake_chat_stream(messages, client_id=None):
        call_count["n"] += 1
        if call_count["n"] == 1:
            yield '###TRANSPARENCY_LOG### {"test": true}\n###RISK_REVIEW### {"approval_required": false, "conflict_with_rag": false}\n###TOOL_CALL### {"name": "GET_PENSION_PRODUCTS", "arguments": {}}'
            return
        yield "PASS - הסבר QA ללא כלים\nסיכום קצר"

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    def fake_execute_tool_call(*args, **kwargs) -> str:
        raise AssertionError("execute_tool_call should not be invoked in no-tools intent")

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [
                {
                    "role": "user",
                    "content": "הסבר במילים בלבד בלי כלים.",
                }
            ],
        },
    )

    assert response.status_code == 200
    assert "###TOOL_CALL###" not in response.text


def test_stream_intent_report_emits_ui_action_only_and_optional_exact_qa(monkeypatch) -> None:
    tool_calls: list[str] = []

    def fake_execute_tool_call(
        *,
        tool_name: str,
        args: dict,
        client_id: int,
        db,
        pension_portfolio=None,
        force_max_exemption: bool = False,
        agent_reply: str | None = None,
        user_approved: bool = False,
        request_id: str | None = None,
    ) -> str:
        tool_calls.append(tool_name)
        if tool_name == "GENERATE_FULL_REPORT":
            return json.dumps(
                {
                    "success": True,
                    "client_id": client_id,
                    "open_path": f"/clients/{client_id}/reports?auto_html=1",
                    "status_message": "הדוח נוצר בהצלחה",
                },
                ensure_ascii=False,
            )
        return json.dumps({"success": True}, ensure_ascii=False)

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called in REPORT intent")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [
                {
                    "role": "user",
                    "content": "אנא הפק דוח מלא (QA)",
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.text
    assert "###UI_ACTION###" in body
    assert "###END_UI_ACTION###" in body
    assert "PASS - סיכום QA סופי לאחר יצירת הדוח" in body
    assert "###TOOL_CALL###" not in body
    assert tool_calls == ["GENERATE_FULL_REPORT"]


def test_stream_intent_report_without_qa_emits_ui_action_only(monkeypatch) -> None:
    tool_calls: list[str] = []

    def fake_execute_tool_call(
        *,
        tool_name: str,
        args: dict,
        client_id: int,
        db,
        pension_portfolio=None,
        force_max_exemption: bool = False,
        agent_reply: str | None = None,
        user_approved: bool = False,
        request_id: str | None = None,
    ) -> str:
        tool_calls.append(tool_name)
        return json.dumps(
            {
                "success": True,
                "client_id": client_id,
                "open_path": f"/clients/{client_id}/reports?auto_html=1",
                "status_message": "הדוח נוצר בהצלחה",
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called in REPORT intent")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [
                {
                    "role": "user",
                    "content": "שלח דוח מסכם",
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.text
    assert "###UI_ACTION###" in body
    assert "###END_UI_ACTION###" in body
    assert "PASS - סיכום QA סופי לאחר יצירת הדוח" not in body
    assert "###TOOL_CALL###" not in body
    assert tool_calls == ["GENERATE_FULL_REPORT"]


def test_stream_intent_analysis_allows_tool_execution(monkeypatch) -> None:
    call_count = {"n": 0}

    def fake_chat_stream(messages, client_id=None):
        call_count["n"] += 1
        if call_count["n"] == 1:
            yield '###TRANSPARENCY_LOG### {"test": true}\n###RISK_REVIEW### {"approval_required": false, "conflict_with_rag": false}\n###TOOL_CALL### {"name": "GET_PENSION_PRODUCTS", "arguments": {}}'
            return
        raise AssertionError("ANALYSIS stop-after-tool: LLM should not be called again")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    tool_calls: list[str] = []

    def fake_execute_tool_call(
        *,
        tool_name: str,
        args: dict,
        client_id: int,
        db,
        pension_portfolio=None,
        force_max_exemption: bool = False,
        agent_reply: str | None = None,
        user_approved: bool = False,
        request_id: str | None = None,
    ) -> str:
        tool_calls.append(tool_name)
        return json.dumps({"success": True}, ensure_ascii=False)

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [
                {
                    "role": "user",
                    "content": "ניתוח ותיזמון פרישה",
                }
            ],
        },
    )

    assert response.status_code == 200
    assert tool_calls == ["GET_PENSION_PRODUCTS"]
    assert "הפקתי את תוצאות הניתוח מהמערכת" in response.text
