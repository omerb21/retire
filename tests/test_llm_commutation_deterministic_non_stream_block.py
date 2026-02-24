import json

import app.services.llm_chat.chat_orchestration as chat_orch
from app.schemas.llm_chat import ChatMessage, ChatRequest
from app.services.llm_chat.chat_orchestration import run_pension_chat


def test_non_stream_commutation_request_does_not_trigger_deterministic_transform(
    monkeypatch, db_session
) -> None:
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
            {"success": True, "pension_fund_id": 1, "commutation_asset_id": 2},
            ensure_ascii=False,
        )

    monkeypatch.setattr(chat_orch, "execute_tool_call", fake_execute_tool_call)

    # If orchestration is correct, it will not call LLM at all for this path.
    def fake_chat(messages, client_id=None):
        return "final"

    monkeypatch.setattr(chat_orch.pension_llm_service, "chat", fake_chat)

    req = ChatRequest(
        messages=[
            ChatMessage(
                role="user",
                content="מעוניין לבצע היוון קצבה של כל היתרה של תכנית כלל תמר(10416027)",
            )
        ],
        client_id=1,
        pension_portfolio=[
            {
                "מספר_חשבון": "10416027",
                "שם_תכנית": "כלל תמר",
                "חברה_מנהלת": "כלל",
                "סוג_מוצר": "קרן פנסיה",
                "יתרה": 100000,
            }
        ],
    )

    resp = run_pension_chat(req, db_session)

    assert "TRANSFORM_FUNDS_TO_ASSETS" not in tool_calls
    assert isinstance(resp.reply, str)
    assert "קצבה קיימת במערכת" in resp.reply

    from app.models.pension_fund import PensionFund

    pf = (
        db_session.query(PensionFund)
        .filter(PensionFund.client_id == 1)
        .filter(PensionFund.deduction_file == "10416027")
        .first()
    )
    assert pf is None
