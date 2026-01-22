import json
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app
from app.models.capital_asset import CapitalAsset
from app.models.client import Client
from app.services.llm_chat.pending_approvals import store_pending_approval_ui_action


def test_stream_user_approved_args_hash_mismatch_refuses(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]

    with Session() as db:
        client = db.query(Client).filter(Client.id == 920000001).first()
        if client is None:
            client = Client(
                id=920000001,
                id_number_raw="920000001",
                id_number="920000001",
                full_name="Test User",
                birth_date=date(1980, 1, 1),
            )
            db.add(client)
            db.flush()
        client_id = int(getattr(client, "id", 0) or 0)

        # Create a conversion-looking asset; lock should not matter for refusal path.
        db.add(
            CapitalAsset(
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
        )

        stored_args = {
            "accounts": [{"account_id": "A", "amount": 1}],
            "use_provided_accounts_only": True,
        }
        store_ok = store_pending_approval_ui_action(
            db=db,
            client_id=client_id,
            request_kind="execute_target_plan",
            tool_name="TRANSFORM_FUNDS_TO_ASSETS",
            tool_args=stored_args,
            ui_action="dummy",
        )
        assert store_ok is True
        db.commit()

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called when user approval marker is present")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    def fake_execute_tool_call(*args, **kwargs) -> str:
        raise AssertionError("Tool must not be executed on args_hash mismatch")

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)

    approved_args = {
        "accounts": [{"account_id": "A", "amount": 2}],  # different amount -> mismatch
        "use_provided_accounts_only": True,
    }
    resp = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [
                {
                    "role": "user",
                    "content": f"###USER_APPROVED### {json.dumps({'tool_name': 'TRANSFORM_FUNDS_TO_ASSETS', 'arguments': approved_args}, ensure_ascii=False)}",
                }
            ],
            "pension_portfolio": [],
        },
    )

    assert resp.status_code == 200
    body = resp.text
    assert "אין בקשת אישור פתוחה תואמת" in body
    assert "טיפ: לחץ על אשר מתוך חלון האישור" in body
    assert "🔧" not in body
    assert "###UI_ACTION###" not in body
