import json
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app
from app.models.capital_asset import CapitalAsset
from app.models.client import Client


def test_stream_no_auto_replan_after_transform(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]
    with Session() as db:
        client = db.query(Client).filter(Client.id == 900000010).first()
        if client is None:
            client = Client(
                id=900000010,
                id_number_raw="900000010",
                id_number="900000010",
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
        raise AssertionError("LLM must not be called when post-conversion lock is active")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    def fake_execute_tool_call(*args, **kwargs) -> str:
        raise AssertionError("execute_tool_call must not be invoked when post-conversion lock is active")

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "בנה תכנית פרישה"}],
        },
    )

    assert response.status_code == 200
    body = response.text
    assert "###UI_ACTION###" not in body
    assert "🔧" not in body
    assert "כדי לבנות תכנית פרישה אני צריך יעד חודשי נטו" in body
