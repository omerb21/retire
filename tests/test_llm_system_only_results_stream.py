import json

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def test_stream_system_results_bypasses_llm_and_uses_get_products_tool(monkeypatch) -> None:
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
        assert tool_name == "GET_PENSION_PRODUCTS"
        return json.dumps(
            {
                "products": [
                    {"category": "pension", "fund_name": "פנסיה א", "balance": 1000},
                    {"category": "capital", "asset_name": "הון ב", "current_value": 2000},
                ]
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
    assert "רשימת מוצרים" in body
    assert tool_calls and tool_calls[0][0] == "GET_PENSION_PRODUCTS"
