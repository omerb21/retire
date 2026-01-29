import json
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app
from app.models.capital_asset import CapitalAsset
from app.models.client import Client


def test_stream_post_conversion_lock_blocks_plan_build(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]
    with Session() as db:
        client = db.query(Client).filter(Client.id == 900000002).first()
        if client is None:
            client = Client(
                id=900000002,
                id_number_raw="900000002",
                id_number="900000002",
                full_name="Test User",
                birth_date=date(1980, 1, 1),
            )
            db.add(client)
            db.flush()
        client_id = int(getattr(client, "id", 0) or 0)

        asset = CapitalAsset(
            client_id=client_id,
            asset_name="Converted",
            asset_type="provident_fund",
            current_value=Decimal("0"),
            monthly_income=Decimal("0"),
            annual_return_rate=Decimal("0.04"),
            payment_frequency="annually",
            start_date=date(2020, 1, 1),
            indexation_method="none",
            tax_treatment="taxable",
            conversion_source=json.dumps({"source": "scenario_conversion"}, ensure_ascii=False),
        )
        db.add(asset)
        db.commit()

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for tools-first plan request")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    seen = {"called": 0}

    def fake_execute_tool_call(*args, **kwargs) -> str:
        seen["called"] += 1
        tool_name = None
        if args:
            tool_name = args[0]
        if tool_name is None:
            tool_name = kwargs.get("tool_name")
        assert tool_name == "BUILD_TARGET_PENSION_PLAN"
        return json.dumps(
            {"success": True, "tool_name": tool_name, "result": {"ok": True}, "explanation": "OK"},
            ensure_ascii=False,
        )

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [
                {"role": "user", "content": "צור תכנית פרישה לקצבת יעד של 29000 נטו"}
            ],
        },
    )

    assert response.status_code == 200
    body = response.text
    assert "###UI_ACTION###" not in body
    assert "כותרת: תכנית לאחר המרה" not in body
    assert "🔧" in body
    assert int(seen.get("called") or 0) > 0
