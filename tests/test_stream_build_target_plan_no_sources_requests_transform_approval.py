import json
from datetime import date, datetime, timezone

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app
from app.models.client import Client
from app.models.scenario import Scenario
from app.services.llm_agent_tools_service import AgentToolsService


def test_stream_build_target_plan_no_sources_requests_transform_approval(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]

    client_id = 950000001

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

        snapshot_accounts = [
            {
                "מספר_חשבון": "A1",
                "שם_תכנית": "Fund A",
                "חברה_מנהלת": "X",
                "סוג_מוצר": "קופת גמל",
                "יתרה": 100000,
                "תאריך_התחלה": "2005-01-01",
                "תגמולים": 100000,
            }
        ]
        db.add(
            Scenario(
                client_id=client_id,
                scenario_name="pension_portfolio_snapshot",
                apply_tax_planning=False,
                apply_capitalization=False,
                apply_exemption_shield=False,
                parameters=json.dumps({"pension_portfolio": snapshot_accounts}, ensure_ascii=False),
                created_at=datetime.now(timezone.utc),
            )
        )
        db.commit()

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for tools-first plan request")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    def fake_build_target_pension_plan(
        self, target_monthly_pension, target_is_net, retirement_age=None, ignore_blocked_balances=True
    ):
        return {
            "success": False,
            "tool_name": "BUILD_TARGET_PENSION_PLAN",
            "result": {},
            "explanation": "לא נמצאו מקורות קצבה (קרנות פנסיה או נכסי הון) ללקוח.",
        }

    monkeypatch.setattr(AgentToolsService, "build_target_pension_plan", fake_build_target_pension_plan)

    api = TestClient(app)
    resp = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "בנה תכנית יעד קצבה יעד נטו 30000"}],
            "pension_portfolio": [],
        },
    )

    assert resp.status_code == 200
    body = resp.text
    assert "Tool Error" not in body
    assert "###UI_ACTION###" in body
    assert "approval_request" in body
    assert "TRANSFORM_FUNDS_TO_ASSETS" in body

    start = body.find("###UI_ACTION###")
    end = body.find("###END_UI_ACTION###")
    assert start >= 0
    assert end > start
    ui_payload = json.loads(body[start + len("###UI_ACTION###") : end])
    assert ui_payload.get("type") == "ui_actions"
    actions = ui_payload.get("actions")
    assert isinstance(actions, list) and actions
    approval = actions[0]
    assert approval.get("type") == "approval_request"
    assert approval.get("tool_name") == "TRANSFORM_FUNDS_TO_ASSETS"
    args = approval.get("arguments")
    assert isinstance(args, dict)
    assert isinstance(args.get("accounts"), list) and len(args.get("accounts")) > 0
    assert args.get("use_provided_accounts_only") is True
    assert args.get("ignore_blocked_balances") is True
    assert args.get("skip_non_convertible_accounts") is True

    with Session() as db:
        pending = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "pending_approval")
            .order_by(Scenario.created_at.desc())
            .first()
        )
        assert pending is not None
        pending_payload = json.loads(pending.parameters)
        assert pending_payload.get("tool_name") == "TRANSFORM_FUNDS_TO_ASSETS"
        pending_args = pending_payload.get("arguments")
        assert isinstance(pending_args, dict)
        assert isinstance(pending_args.get("accounts"), list) and len(pending_args.get("accounts")) > 0
        resume = pending_args.get("_after_build_target_pension_plan_args")
        assert isinstance(resume, dict) and resume
        assert resume.get("target_monthly_pension") is not None
        assert resume.get("target_is_net") is True
