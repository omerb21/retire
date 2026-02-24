import json
from datetime import date

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app
from app.models.client import Client
from app.models.scenario import Scenario


def test_transform_stream_appends_next_step_hint(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for deterministic transform")

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

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
        assert tool_name == "TRANSFORM_FUNDS_TO_ASSETS"
        return json.dumps(
            {
                "success": True,
                "total_converted": 1,
                "converted_pensions": 1,
                "converted_capitals": 0,
                "converted_items": [
                    {
                        "kind": "pension",
                        "account_name": "תכנית",
                        "account_number": "A-001",
                        "amount": 1000,
                        "tax_treatment": "taxable",
                        "components": {"תגמולי_עובד_אחרי_2000": 1000},
                    }
                ],
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    resp = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [{"role": "user", "content": "המר"}],
            "pension_portfolio": [
                {
                    "מספר_חשבון": "A-001",
                    "שם_תכנית": "תכנית",
                    "סוג_מוצר": "קופת גמל",
                    "יתרה": 1000,
                    "specific_amounts": {"תגמולי_עובד_אחרי_2000": 1000},
                }
            ],
        },
    )
    assert resp.status_code == 200
    assert "השלב הבא המומלץ: הפקת דוח" in resp.text


def test_report_blocked_when_latest_snapshot_is_not_transform(
    monkeypatch, _test_db
) -> None:
    Session = _test_db["Session"]

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for deterministic report gating")

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

    def fake_execute_tool_call(*args, **kwargs):
        raise AssertionError("Report tool must not be executed when gated")

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    with Session() as db:
        client = db.query(Client).filter(Client.id == 930400001).first()
        if client is None:
            client = Client(
                id=930400001,
                id_number_raw="930400001",
                id_number="930400001",
                full_name="Test User",
                birth_date=date(1980, 1, 1),
            )
            db.add(client)
            db.flush()
        client_id = int(getattr(client, "id", 0) or 0)

        snap = Scenario(
            client_id=client_id,
            scenario_name="pension_portfolio_snapshot",
            apply_tax_planning=False,
            apply_capitalization=False,
            apply_exemption_shield=False,
            parameters=json.dumps(
                {
                    "pension_portfolio": [],
                    "_meta": {"operation_type": "restore_snapshot"},
                },
                ensure_ascii=False,
            ),
        )
        db.add(snap)
        db.commit()

    api = TestClient(app)
    resp = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "שלח דוח תוצאות של המערכת"}],
            "pension_portfolio": [],
        },
    )
    assert resp.status_code == 200
    body = resp.text
    assert "###UI_ACTION###" in body
    assert "כדי להפיק דוח חייבים קודם לבצע המרה" in body
    assert f"/clients/{client_id}/pension-portfolio" in body


def test_report_allowed_after_transform_and_replay_is_stable(
    monkeypatch, _test_db
) -> None:
    Session = _test_db["Session"]

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError(
            "LLM must not be called for deterministic system-results report"
        )

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

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
        request_id: str | None = None,
    ) -> str:
        tool_calls.append(tool_name)
        assert tool_name == "GENERATE_FULL_REPORT"
        return json.dumps(
            {
                "success": True,
                "client_id": client_id,
                "open_path": f"/clients/{client_id}/reports?auto_html=1",
                "status_message": "OK",
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    with Session() as db:
        client = db.query(Client).filter(Client.id == 930400002).first()
        if client is None:
            client = Client(
                id=930400002,
                id_number_raw="930400002",
                id_number="930400002",
                full_name="Test User",
                birth_date=date(1980, 1, 1),
            )
            db.add(client)
            db.flush()
        client_id = int(getattr(client, "id", 0) or 0)

        # restore -> transform -> report (latest is transform)
        snap_restore = Scenario(
            client_id=client_id,
            scenario_name="pension_portfolio_snapshot",
            apply_tax_planning=False,
            apply_capitalization=False,
            apply_exemption_shield=False,
            parameters=json.dumps(
                {
                    "pension_portfolio": [],
                    "_meta": {"operation_type": "restore_snapshot"},
                },
                ensure_ascii=False,
            ),
        )
        db.add(snap_restore)
        db.flush()

        snap_transform = Scenario(
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
        )
        db.add(snap_transform)
        db.commit()

    api = TestClient(app)
    payload = {
        "client_id": client_id,
        "messages": [{"role": "user", "content": "שלח דוח תוצאות של המערכת"}],
        "pension_portfolio": [],
    }

    resp1 = api.post("/api/v1/llm/pension-chat-stream", json=payload)
    assert resp1.status_code == 200
    body1 = resp1.text
    assert "###UI_ACTION###" in body1
    assert f"/clients/{client_id}/reports?auto_html=1" in body1

    resp2 = api.post("/api/v1/llm/pension-chat-stream", json=payload)
    assert resp2.status_code == 200
    body2 = resp2.text

    assert body2 == body1
    assert tool_calls == ["GENERATE_FULL_REPORT", "GENERATE_FULL_REPORT"]
