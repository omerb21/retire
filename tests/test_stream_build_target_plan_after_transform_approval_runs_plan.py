import json
from datetime import date, datetime, timezone
import inspect

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app
from app.models.client import Client
from app.models.scenario import Scenario
from app.services.llm_agent_tools_service import AgentToolsService


def test_stream_build_target_plan_after_transform_approval_runs_plan(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]

    client_id = 950000002

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

    phase = {"after_transform": False}

    def fake_build_target_pension_plan(
        self, target_monthly_pension, target_is_net, retirement_age=None, ignore_blocked_balances=True
    ):
        if not phase["after_transform"]:
            return {
                "success": False,
                "tool_name": "BUILD_TARGET_PENSION_PLAN",
                "result": {},
                "explanation": "לא נמצאו מקורות קצבה (קרנות פנסיה או נכסי הון) ללקוח.",
            }
        return {
            "success": True,
            "tool_name": "BUILD_TARGET_PENSION_PLAN",
            "result": {
                "target_monthly_pension": float(target_monthly_pension),
                "target_is_net": bool(target_is_net),
                "retirement_age": int(retirement_age or 67),
                "target_achieved": True,
                "accumulated_pension": 40000,
                "estimated_monthly_tax": 0,
                "estimated_monthly_net": 40000,
                "remaining_capital": 0,
            },
            "explanation": "OK",
        }

    monkeypatch.setattr(AgentToolsService, "build_target_pension_plan", fake_build_target_pension_plan)

    original_execute_tool_call = stream_orch.execute_tool_call

    tool_calls: list[str] = []

    def wrapped_execute_tool_call(
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
        tool_calls.append(tool_name)
        if tool_name == "TRANSFORM_FUNDS_TO_ASSETS":
            assert user_approved is True
            assert isinstance(args.get("accounts"), list) and len(args.get("accounts")) > 0
            assert args.get("use_provided_accounts_only") is True
            assert args.get("ignore_blocked_balances") is True
            assert args.get("skip_non_convertible_accounts") is True
            phase["after_transform"] = True
            return json.dumps(
                {
                    "success": True,
                    "tool_name": tool_name,
                    "total_converted": 1,
                    "converted_pensions": 1,
                },
                ensure_ascii=False,
            )

        sig = inspect.signature(original_execute_tool_call)
        call_kwargs = {
            "tool_name": tool_name,
            "args": args,
            "client_id": client_id,
            "db": db,
            "pension_portfolio": pension_portfolio,
            "force_max_exemption": force_max_exemption,
            "agent_reply": agent_reply,
            "user_approved": user_approved,
            "request_id": request_id,
        }
        filtered = {k: v for k, v in call_kwargs.items() if k in sig.parameters}
        return original_execute_tool_call(**filtered)

    monkeypatch.setattr(stream_orch, "execute_tool_call", wrapped_execute_tool_call)

    api = TestClient(app)

    resp1 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "בנה תכנית יעד קצבה יעד נטו 30000"}],
            "pension_portfolio": [],
        },
    )
    assert resp1.status_code == 200
    assert "###UI_ACTION###" in resp1.text
    assert "TRANSFORM_FUNDS_TO_ASSETS" in resp1.text
    assert "Tool Error" not in resp1.text

    with Session() as db:
        pending = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "pending_approval")
            .order_by(Scenario.created_at.desc())
            .first()
        )
        assert pending is not None

    resp2 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [
                {"role": "user", "content": "מאשר"},
            ],
            "pension_portfolio": [],
        },
    )

    assert resp2.status_code == 200
    body2 = resp2.text
    assert "🔧" in body2
    assert "TRANSFORM_FUNDS_TO_ASSETS" in body2
    assert "בניית תכנית קצבה" in body2
    assert "לא נמצאו מקורות קצבה" not in body2
    assert tool_calls == ["BUILD_TARGET_PENSION_PLAN", "TRANSFORM_FUNDS_TO_ASSETS", "BUILD_TARGET_PENSION_PLAN"]

    with Session() as db:
        pending_after = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "pending_approval")
            .order_by(Scenario.created_at.desc())
            .first()
        )
        assert pending_after is None
