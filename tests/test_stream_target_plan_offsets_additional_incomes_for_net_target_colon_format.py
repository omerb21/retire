import json
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
import app.services.llm_chat.chat_stream_orchestration_parts.orchestrator_impl_parts.stream_loop as stream_loop
from app.main import app
from app.models.additional_income import AdditionalIncome
from app.models.client import Client


def test_stream_target_plan_offsets_additional_incomes_for_net_target_colon_format(
    monkeypatch, _test_db
) -> None:
    Session = _test_db["Session"]

    with Session() as db:
        client = db.query(Client).filter(Client.id == 990000002).first()
        if client is None:
            client = Client(
                id=990000002,
                id_number_raw="990000002",
                id_number="990000002",
                full_name="Test User",
                birth_date=date(1980, 1, 1),
            )
            db.add(client)
            db.flush()
        client_id = int(getattr(client, "id", 0) or 0)

        db.add(
            AdditionalIncome(
                client_id=client_id,
                source_type="rental",
                description="Apt",
                amount=Decimal("1000"),
                frequency="monthly",
                start_date=date(2020, 1, 1),
                end_date=None,
                indexation_method="none",
                fixed_rate=None,
                tax_treatment="exempt",
                tax_rate=None,
                remarks=None,
            )
        )
        db.commit()

    def fake_chat_stream(*args, **kwargs):
        raise AssertionError("LLM must not be called for deterministic target plan build")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    tool_calls: list[tuple[str, dict]] = []

    def fake_execute_tool_call(tool_name: str, args: dict, client_id: int, db, **kwargs) -> str:
        tool_calls.append((tool_name, args))
        assert tool_name == "BUILD_TARGET_PENSION_PLAN"
        payload = {
            "tool_name": "BUILD_TARGET_PENSION_PLAN",
            "args": args,
            "result": {
                "target_achieved": True,
                "plan_steps": [{"step_number": 1}],
                "sources_used": [],
                "execution_plan": {
                    "accounts": [],
                    "target_gross": 0,
                    "target_net": 0,
                    "expected_total_gross": 0,
                    "expected_total_net": 0,
                },
            },
        }
        return (
            "OK\n\n###TARGET_PENSION_PLAN_DATA###\n"
            + json.dumps(payload, ensure_ascii=False)
            + "\n###END_TARGET_PENSION_PLAN_DATA###"
        )

    monkeypatch.setattr(stream_loop, "_execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)

    # Step 1: trigger pending plan target marker (plan request without target)
    resp1 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "בנה תכנית פרישה"}],
            "pension_portfolio": [],
        },
    )
    assert resp1.status_code == 200

    # Step 2: provide target in colon format (this must apply offset)
    resp2 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "יעד נטו: 3000"}],
            "pension_portfolio": [],
        },
    )

    assert resp2.status_code == 200
    body = resp2.text

    assert "✅ חישוב דטרמיניסטי" in body
    assert "קיזוז הכנסות נוספות" in body
    assert "יעד קצבה לתכנית" in body

    assert tool_calls
    _tool_name, args = tool_calls[-1]
    assert float(args.get("target_monthly_pension") or 0) == 3000.0
    assert args.get("target_is_net") is True
