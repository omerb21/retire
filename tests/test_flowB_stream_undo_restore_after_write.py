import json
from datetime import date

from fastapi.testclient import TestClient

from app.main import app
from app.models.client import Client
from app.models.scenario import Scenario

import app.services.llm_chat.chat_stream_orchestration as stream_orch
import app.services.llm_chat.tool_execution as tool_exec


def _extract_ui_action_payload(body: str) -> dict:
    assert "###UI_ACTION###" in body
    payload_json = body.split("###UI_ACTION###", 1)[1].split("###END_UI_ACTION###", 1)[0]
    return json.loads(payload_json)


def test_flowB_stream_undo_restore_after_write(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]

    # Ensure deterministic stream (no LLM)
    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for undo/approval deterministic flow")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    client_id = 950500001
    with Session() as db:
        client = db.query(Client).filter(Client.id == client_id).first()
        if client is None:
            client = Client(
                id=client_id,
                id_number_raw=str(client_id),
                id_number=str(client_id),
                full_name="Test User",
                birth_date=date(1980, 1, 1),
            )
            db.add(client)
            db.flush()
        # clean undo snapshot
        db.query(Scenario).filter(Scenario.client_id == client_id).filter(
            Scenario.scenario_name == "undo_snapshot"
        ).delete(synchronize_session=False)
        # create pending approval for a write tool
        db.query(Scenario).filter(Scenario.client_id == client_id).filter(
            Scenario.scenario_name == "pending_approval"
        ).delete(synchronize_session=False)
        db.add(
            Scenario(
                client_id=client_id,
                scenario_name="pending_approval",
                apply_tax_planning=False,
                apply_capitalization=False,
                apply_exemption_shield=False,
                parameters=json.dumps(
                    {
                        "tool_name": "TRANSFORM_FUNDS_TO_ASSETS",
                        "arguments": {"accounts": [], "use_provided_accounts_only": True},
                    },
                    ensure_ascii=False,
                ),
            )
        )
        db.commit()

    # Avoid real DB mutations from transform, but keep tool_execution path intact.
    def fake_transform(*, args: dict, client_id: int, db, pension_portfolio=None, force_max_exemption: bool = False, agent_reply=None):
        return json.dumps({"success": True, "tool_name": "TRANSFORM_FUNDS_TO_ASSETS"}, ensure_ascii=False)

    monkeypatch.setattr(tool_exec, "handle_transform_funds_to_assets", fake_transform)

    # Capture snapshot deterministically
    def fake_save_snapshot(self, client_id: int, snapshot_name: str = None):
        return {"snapshot": {"data": {"pension_funds": [], "capital_assets": [], "additional_incomes": [], "current_employer": None, "grants": [], "legacy_grants": [], "termination_event": None, "fixation_result": None}}, "success": True}

    monkeypatch.setattr(tool_exec.SnapshotService, "save_snapshot", fake_save_snapshot)

    # Restore should not touch DB in tests
    def fake_restore_snapshot(self, client_id: int, snapshot_data: dict):
        return {"success": True, "message": "restored"}

    monkeypatch.setattr(tool_exec.SnapshotService, "restore_snapshot", fake_restore_snapshot)

    api = TestClient(app)

    # 1) approve pending write tool -> should execute and create undo_snapshot
    resp1 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "מאשר"}],
            "pension_portfolio": [],
        },
    )
    assert resp1.status_code == 200

    with Session() as db:
        undo_row = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "undo_snapshot")
            .order_by(Scenario.created_at.desc(), Scenario.id.desc())
            .first()
        )
        assert undo_row is not None
        undo_id = int(getattr(undo_row, "id", 0) or 0)
        assert undo_id > 0

    # 2) user asks undo -> should return approval_request for restore
    resp2 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "בטל פעולה"}],
        },
    )
    assert resp2.status_code == 200
    payload = _extract_ui_action_payload(resp2.text)
    assert payload.get("actions")[0].get("tool_name") == "RESTORE_SYSTEM_SNAPSHOT"
    assert payload.get("actions")[0].get("arguments").get("snapshot_scenario_id") == undo_id

    # 3) approve restore -> should execute restore and clear undo_snapshot
    resp3 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [
                {
                    "role": "user",
                    "content": f'###USER_APPROVED### {{"tool_name": "RESTORE_SYSTEM_SNAPSHOT", "arguments": {{"snapshot_scenario_id": {undo_id}}}}}',
                }
            ],
        },
    )
    assert resp3.status_code == 200

    with Session() as db:
        undo_after = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "undo_snapshot")
            .first()
        )
        assert undo_after is None
