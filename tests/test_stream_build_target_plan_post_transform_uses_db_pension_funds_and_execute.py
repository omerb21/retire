import json
from datetime import date, datetime, timezone

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app
from app.models.client import Client
from app.models.pension_fund import PensionFund
from app.models.scenario import Scenario


def test_stream_build_target_plan_post_transform_uses_db_pension_funds_and_execute(
    monkeypatch, _test_db
) -> None:
    Session = _test_db["Session"]
    client_id = 996000002

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError(
            "LLM must not be called for deterministic post-transform regression test"
        )

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

    with Session() as db:
        client = db.query(Client).filter(Client.id == client_id).first()
        if client is None:
            client = Client(
                id=client_id,
                id_number_raw=str(client_id),
                id_number=str(client_id),
                full_name="Test User",
                birth_date=date(1980, 1, 1),
                gender="male",
                is_active=True,
            )
            db.add(client)
            db.flush()

        db.query(Scenario).filter(Scenario.client_id == client_id).filter(
            Scenario.scenario_name.in_(
                [
                    "target_pension_plan",
                    "target_pension_plan_data",
                    "pension_portfolio_snapshot",
                ]
            )
        ).delete(synchronize_session=False)

        # Mark last snapshot as post-transform (can be empty; we rely on DB funds).
        db.add(
            Scenario(
                client_id=client_id,
                scenario_name="pension_portfolio_snapshot",
                apply_tax_planning=False,
                apply_capitalization=False,
                apply_exemption_shield=False,
                parameters=json.dumps(
                    {
                        "pension_portfolio": [],
                        "_meta": {"operation_type": "TRANSFORM_FUNDS_TO_ASSETS"},
                    },
                    ensure_ascii=False,
                ),
                created_at=datetime.now(timezone.utc),
            )
        )

        # Seed DB with pension funds created by TRANSFORM_FUNDS_TO_ASSETS.
        # They have pension_amount>0 (as created by the pipeline) but should still be treated as executable sources.
        src_json_1 = json.dumps(
            {
                "source": "llm_transform_funds_to_assets",
                "type": "funds_to_assets_conversion",
                "account_number": "A-101",
            },
            ensure_ascii=False,
        )
        src_json_2 = json.dumps(
            {
                "source": "llm_transform_funds_to_assets",
                "type": "funds_to_assets_conversion",
                "account_number": "A-202",
            },
            ensure_ascii=False,
        )

        db.add(
            PensionFund(
                client_id=client_id,
                fund_name="Fund A",
                fund_type="קופת גמל",
                input_mode="manual",
                balance=200000,
                annuity_factor=200,
                pension_amount=1000,
                tax_treatment="taxable",
                deduction_file="A-101",
                conversion_source=src_json_1,
            )
        )
        db.add(
            PensionFund(
                client_id=client_id,
                fund_name="Fund B",
                fund_type="קרן פנסיה",
                input_mode="manual",
                balance=300000,
                annuity_factor=200,
                pension_amount=1500,
                tax_treatment="taxable",
                deduction_file="A-202",
                conversion_source=src_json_2,
            )
        )
        db.commit()

    api = TestClient(app)

    # 1) build: should persist SSOT with execution_plan.accounts derived from DB pension_funds.
    resp1 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [
                {"role": "user", "content": "בנה תכנית יעד קצבה יעד נטו 30000"}
            ],
            "pension_portfolio": [],
        },
    )
    assert resp1.status_code == 200

    with Session() as db:
        ssot = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "target_pension_plan")
            .order_by(Scenario.created_at.desc())
            .first()
        )
        assert ssot is not None
        payload = json.loads(ssot.parameters)
        exec_plan = payload.get("result", {}).get("execution_plan", {})
        assert isinstance(exec_plan.get("accounts"), list)
        assert len(exec_plan.get("accounts")) > 0

    # 2) execute: must return approval UI action, since execution_plan.accounts exists.
    resp2 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "בצע את התכנית"}],
            "pension_portfolio": [],
        },
    )
    assert resp2.status_code == 200
    assert "###UI_ACTION###" in resp2.text
    assert "TRANSFORM_FUNDS_TO_ASSETS" in resp2.text
    assert "לא הצלחתי לגזור" not in resp2.text
