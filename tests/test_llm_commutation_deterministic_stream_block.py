import json

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def test_stream_commutation_request_does_not_trigger_deterministic_transform(monkeypatch, db_session) -> None:
    # Even if the LLM would later suggest transforms, the stream orchestration must
    # intercept commutation intent early and never run TRANSFORM_FUNDS_TO_ASSETS.

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
    ) -> str:
        tool_calls.append(tool_name)
        return json.dumps(
            {
                "success": True,
                "pension_fund_id": 1,
                "commutation_asset_id": 2,
                "commutation_amount": float(args.get("commutation_amount") or 0),
                "portfolio_account_number": "10416027",
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    # Avoid hitting LLM at all; if orchestration is correct, it will execute tool directly.
    def fake_chat_stream(messages, client_id=None):
        yield "final"

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [
                {
                    "role": "user",
                    "content": "מעוניין לבצע היוון קצבה של כל היתרה של תכנית כלל תמר(10416027)",
                }
            ],
            "pension_portfolio": [
                {
                    "מספר_חשבון": "10416027",
                    "שם_תכנית": "כלל תמר",
                    "חברה_מנהלת": "כלל",
                    "סוג_מוצר": "קרן פנסיה",
                    "יתרה": 100000,
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.text
    assert "TRANSFORM_FUNDS_TO_ASSETS" not in tool_calls
    assert "קצבה קיימת במערכת" in body

    from app.models.pension_fund import PensionFund

    pf = (
        db_session.query(PensionFund)
        .filter(PensionFund.client_id == 1)
        .filter(PensionFund.deduction_file == "10416027")
        .first()
    )
    assert pf is None
