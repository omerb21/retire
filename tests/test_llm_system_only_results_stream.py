import json

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def test_stream_system_results_bypasses_llm_and_uses_cashflow_tool(monkeypatch) -> None:
    # If the LLM is called, the test must fail.
    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM should not be called for system results requests")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    tool_calls: list[tuple[str, dict]] = []

    def fake_execute_tool_call(
        *,
        tool_name: str,
        args: dict,
        client_id: int,
        db,
        pension_portfolio=None,
        force_max_exemption: bool = False,
    ) -> str:
        tool_calls.append((tool_name, args))
        assert tool_name == "RUN_RETIREMENT_CASHFLOW_ANALYSIS"
        # Return a minimal shape compatible with _format_system_results_from_cashflow.
        return json.dumps(
            {
                "retirement_date": args.get("retirement_date"),
                "retirement_age": 72,
                "projected_pension": 49327.2,
                "monthly_tax_deduction": 13552.89,
                "projected_pension_net": 35774.32,
                "exemption_percentage": 0.0,
                "exempt_pension_monthly": 0.0,
                "total_liquid_capital": 35475.0,
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    # Avoid any DB snapshot loading.
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
            "messages": [{"role": "user", "content": "מה גובה סה\"כ הקצבה כעת?"}],
        },
    )

    assert response.status_code == 200
    body = response.text
    assert "תוצאות בפועל במערכת" in body
    assert "קצבה ברוטו" in body
    assert tool_calls and tool_calls[0][0] == "RUN_RETIREMENT_CASHFLOW_ANALYSIS"
