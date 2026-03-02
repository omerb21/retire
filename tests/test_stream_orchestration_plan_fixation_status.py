import json

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def test_stream_orchestration_plan_fixation_status_uses_tool_no_llm(
    monkeypatch,
) -> None:
    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for fixation status orchestration")

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

    tool_calls: list[tuple[str, dict]] = []

    def fake_execute_tool_call(
        *,
        tool_name: str,
        args: dict,
        client_id: int,
        db,
        pension_portfolio=None,
        force_max_exemption: bool = False,
    ):
        tool_calls.append((tool_name, args))
        assert tool_name == "GET_FIXATION_STATUS_SNAPSHOT"
        return json.dumps(
            {
                "has_prior_fixation": "no",
                "has_161": "unknown",
                "has_161d": "no",
                "has_commutation": "unknown",
                "has_exempt_grants": "unknown",
                "employment_ended": "unknown",
                "missing_inputs": ["אין מסמכי 161ד"],
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    def fake_load_latest_pension_portfolio_snapshot_models(db, client_id):
        return None

    monkeypatch.setattr(
        stream_orch,
        "load_latest_pension_portfolio_snapshot_models",
        fake_load_latest_pension_portfolio_snapshot_models,
    )

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [{"role": "user", "content": "סטטוס קיבוע"}],
        },
    )

    assert response.status_code == 200
    body = response.text

    assert tool_calls and len(tool_calls) == 1
    assert "כותרת: סטטוס קיבוע זכויות במערכת" in body
    assert "###UI_ACTION###" not in body
    assert "🔧" in body
