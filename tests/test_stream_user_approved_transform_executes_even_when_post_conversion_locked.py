import json
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app
from app.models.capital_asset import CapitalAsset
from app.models.client import Client
from app.models.scenario import Scenario
from app.services.llm_chat.pending_approvals import store_pending_approval_ui_action


def test_stream_user_approved_transform_executes_even_when_post_conversion_locked(
    monkeypatch, _test_db
) -> None:
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

        # Force POST_CONVERSION_LOCKED state
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
            conversion_source=json.dumps(
                {"source": "scenario_conversion"}, ensure_ascii=False
            ),
        )
        db.add(asset)

        tool_args = {
            "accounts": [{"account_id": "A", "amount": 1}],
            "use_provided_accounts_only": True,
            "ignore_blocked_balances": True,
            "skip_non_convertible_accounts": True,
        }
        store_ok = store_pending_approval_ui_action(
            db=db,
            client_id=client_id,
            request_kind="execute_target_plan",
            tool_name="TRANSFORM_FUNDS_TO_ASSETS",
            tool_args=tool_args,
            ui_action="dummy",
        )
        assert store_ok is True
        db.commit()

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError(
            "LLM must not be called when user approval marker is present"
        )

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
        agent_reply: str | None = None,
        user_approved: bool = False,
        request_id: str | None = None,
    ) -> str:
        tool_calls.append((tool_name, args))
        assert tool_name == "TRANSFORM_FUNDS_TO_ASSETS"
        assert user_approved is True
        return json.dumps({"success": True}, ensure_ascii=False)

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [
                {
                    "role": "user",
                    "content": f"###USER_APPROVED### {json.dumps({'tool_name': 'TRANSFORM_FUNDS_TO_ASSETS', 'arguments': tool_args}, ensure_ascii=False)}",
                }
            ],
        },
    )

    assert response.status_code == 200
    assert tool_calls == [("TRANSFORM_FUNDS_TO_ASSETS", tool_args)]

    body = response.text
    assert "🔧" in body
    assert "כותרת: מצב תיק לאחר המרה" not in body
    assert "השלב הבא המומלץ: הפקת דוח" in body
    assert body.rfind("success") < body.rfind("השלב הבא המומלץ: הפקת דוח")

    with Session() as db:
        pending = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "pending_approval")
            .order_by(Scenario.created_at.desc())
            .first()
        )
        assert pending is None
