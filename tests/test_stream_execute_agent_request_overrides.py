import pytest
from fastapi.testclient import TestClient

from app.main import app


def _install_fake_mcp(monkeypatch, *, reason_code: str):
    import app.services.llm_chat.mcp.engine as mcp_engine
    from app.services.llm_chat.mcp.types import (
        MCPDecision,
        MCPExecutionMode,
        MCPOutcomeFinal,
    )

    def _fake_evaluate(self, *args, **kwargs):
        _ = (self, args, kwargs)
        return MCPDecision(
            execution_mode=MCPExecutionMode.TOOL_BLOCKED,
            reason_code=reason_code,
            capability_id="default_qa_v1",
            intent_tier="QA",
            intent_type="qa",
            outcome_final=MCPOutcomeFinal.TOOL_BLOCKED,
        )

    monkeypatch.setattr(mcp_engine.MCPEngine, "evaluate", _fake_evaluate)


def _install_fake_legacy_stream(monkeypatch, *, body_text: str):
    from fastapi.responses import StreamingResponse

    import app.services.llm_chat.chat_orchestration as chat_orch

    def _fake_run_pension_chat_stream(request, db):
        _ = (request, db)
        return StreamingResponse(iter([body_text]), media_type="text/plain")

    monkeypatch.setattr(
        chat_orch, "run_pension_chat_stream", _fake_run_pension_chat_stream
    )


@pytest.mark.parametrize("reason_code", ["conceptual", "conceptual_form"])
def test_override_allows_legacy_when_reason_code_startswith_conceptual(
    monkeypatch, reason_code: str
) -> None:
    _install_fake_mcp(monkeypatch, reason_code=reason_code)
    _install_fake_legacy_stream(
        monkeypatch, body_text=f"LEGACY_CONCEPTUAL::{reason_code}"
    )

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [
                {"role": "user", "content": "בקיבוע זכויות מה התפקיד של טופס 161ד"}
            ],
        },
    )

    assert response.status_code == 200
    body = response.text

    assert f"LEGACY_CONCEPTUAL::{reason_code}" in body
    assert "הבקשה נחסמה לפי מדיניות" not in body


def test_override_allows_target_plan_approval_ui_action(monkeypatch) -> None:
    _install_fake_mcp(monkeypatch, reason_code="router_no_tools")
    _install_fake_legacy_stream(
        monkeypatch, body_text="###UI_ACTION### approval_request"
    )

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 2,
            "messages": [{"role": "user", "content": "בצע תכנית"}],
        },
    )

    assert response.status_code == 200
    body = response.text

    assert "###UI_ACTION###" in body
    assert "הבקשה נחסמה לפי מדיניות" not in body


def test_override_allows_max_capital_execute_approval_ui_action(monkeypatch) -> None:
    _install_fake_mcp(monkeypatch, reason_code="router_no_tools")
    import app.services.llm_chat.orchestration_utils_parts.guards_and_validations as guards

    monkeypatch.setattr(guards, "is_max_capital_request", lambda _text: True)
    _install_fake_legacy_stream(
        monkeypatch, body_text="###UI_ACTION### approval_request"
    )

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 777002,
            "messages": [{"role": "user", "content": "בצע"}],
        },
    )

    assert response.status_code == 200
    body = response.text

    assert "###UI_ACTION###" in body
    assert "הבקשה נחסמה לפי מדיניות" not in body


def test_negative_router_no_tools_without_text_does_not_allow_ui_action(
    monkeypatch,
) -> None:
    _install_fake_mcp(monkeypatch, reason_code="router_no_tools")

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 3,
            "messages": [{"role": "user", "content": "בצע"}],
        },
    )

    assert response.status_code == 200
    body = response.text

    assert "###UI_ACTION###" not in body
    assert ("הבקשה נחסמה לפי מדיניות" in body) or ("לא נמצאה בקשת אישור פעילה" in body)
