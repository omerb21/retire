import json
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app
from app.models.capital_asset import CapitalAsset
from app.models.client import Client
from app.models.scenario import Scenario
from app.services.llm_chat.chat_orchestration_helpers import store_pending_approval_request


def _extract_ui_action_payload(body: str) -> dict:
    assert "###UI_ACTION###" in body
    payload_json = body.split("###UI_ACTION###", 1)[1].split("###END_UI_ACTION###", 1)[0]
    return json.loads(payload_json)


def test_stream_restore_unlocks_allows_transform_approval_again(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]

    # Guardrail: LLM must not be called in this deterministic flow
    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called in restore/unlock deterministic flow")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    with Session() as db:
        client = db.query(Client).filter(Client.id == 920200001).first()
        if client is None:
            client = Client(
                id=920200001,
                id_number_raw="920200001",
                id_number="920200001",
                full_name="Test User",
                birth_date=date(1980, 1, 1),
            )
            db.add(client)
            db.flush()
        client_id = int(getattr(client, "id", 0) or 0)

        # Force POST_CONVERSION_LOCKED state before restore
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

        # Provide a snapshot that can be restored
        source_snapshot_params = {
            "pension_portfolio": [{"account_number": "A", "יתרה": 100}],
            "_meta": {"operation_type": "pension_portfolio_upload", "trace_id": "t1"},
        }
        source_snapshot = Scenario(
            client_id=client_id,
            scenario_name="pension_portfolio_snapshot",
            apply_tax_planning=False,
            apply_capitalization=False,
            apply_exemption_shield=False,
            parameters=json.dumps(source_snapshot_params, ensure_ascii=False),
        )
        db.add(source_snapshot)
        db.flush()
        source_snapshot_id = int(getattr(source_snapshot, "id", 0) or 0)
        assert source_snapshot_id > 0

        # Provide a latest target plan in DB so execute-target-plan can build transform args
        target_plan_payload = {
            "result": {
                "sources_used": [
                    {
                        "source_type": "pension_fund_from_portfolio",
                        "account_number": "A",
                        "component_field": "תגמולים",
                        "balance_used": 1000,
                        "annuity_factor": 200,
                        "pension_used": 5,
                        "fund_type": "קופת גמל",
                        "company": "X",
                        "plan_name": "Plan",
                    }
                ]
            }
        }
        target_plan = Scenario(
            client_id=client_id,
            scenario_name="target_pension_plan",
            apply_tax_planning=False,
            apply_capitalization=False,
            apply_exemption_shield=False,
            parameters=json.dumps(target_plan_payload, ensure_ascii=False),
        )
        db.add(target_plan)

        # Create pending approval for restore so USER_APPROVED is accepted
        restore_args = {"snapshot_scenario_id": source_snapshot_id, "safety_mode": "strict"}
        assert (
            store_pending_approval_request(
                db=db,
                client_id=client_id,
                tool_name="RESTORE_PENSION_PORTFOLIO_SNAPSHOT",
                tool_args=restore_args,
            )
            is True
        )

        db.commit()

    api = TestClient(app)

    # 1) USER_APPROVED restore executes and creates a restore_snapshot latest snapshot
    restore_resp = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [
                {
                    "role": "user",
                    "content": f"###USER_APPROVED### {json.dumps({'tool_name': 'RESTORE_PENSION_PORTFOLIO_SNAPSHOT', 'arguments': restore_args}, ensure_ascii=False)}",
                }
            ],
        },
    )
    assert restore_resp.status_code == 200
    assert "🔧" in restore_resp.text

    # 2) Now execute target plan should return approval_request for TRANSFORM_FUNDS_TO_ASSETS (no lock message)
    exec_resp = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "בצע את התכנית בפועל"}],
        },
    )
    assert exec_resp.status_code == 200
    body = exec_resp.text
    assert "כותרת: מצב תיק לאחר המרה" not in body
    payload = _extract_ui_action_payload(body)
    actions = payload.get("actions") or []
    assert isinstance(actions, list) and actions
    approval = actions[0]
    assert approval.get("type") == "approval_request"
    assert approval.get("tool_name") == "TRANSFORM_FUNDS_TO_ASSETS"
