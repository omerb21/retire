import json
from datetime import date

from fastapi.testclient import TestClient

from app.main import app
from app.models.client import Client
from app.models.scenario import Scenario

import app.services.llm_chat.tool_execution as tool_exec
from app.services.snapshot_service import SnapshotService


def _extract_ui_action_payload(body: str) -> dict:
    assert "###UI_ACTION###" in body
    payload_json = body.split("###UI_ACTION###", 1)[1].split("###END_UI_ACTION###", 1)[0]
    return json.loads(payload_json)


def test_flowB_non_stream_undo_restore(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]

    client_id = 950500003
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

        # Create an undo_snapshot marker directly
        db.query(Scenario).filter(Scenario.client_id == client_id).filter(
            Scenario.scenario_name == "undo_snapshot"
        ).delete(synchronize_session=False)
        undo = Scenario(
            client_id=client_id,
            scenario_name="undo_snapshot",
            apply_tax_planning=False,
            apply_capitalization=False,
            apply_exemption_shield=False,
            parameters=json.dumps(
                {
                    "snapshot": {
                        "data": {
                            "pension_funds": [],
                            "capital_assets": [],
                            "additional_incomes": [],
                            "current_employer": None,
                            "grants": [],
                            "legacy_grants": [],
                            "termination_event": None,
                            "fixation_result": None,
                        }
                    }
                },
                ensure_ascii=False,
            ),
        )
        db.add(undo)
        db.commit()
        undo_id = int(getattr(undo, "id", 0) or 0)

    def fake_restore_snapshot(self, client_id: int, snapshot_data: dict):
        return {"success": True, "message": "restored"}

    monkeypatch.setattr(SnapshotService, "restore_snapshot", fake_restore_snapshot)

    api = TestClient(app)

    # 1) Ask undo -> should return approval request
    resp1 = api.post(
        "/api/v1/llm/pension-chat",
        json={"client_id": client_id, "messages": [{"role": "user", "content": "undo"}]},
    )
    assert resp1.status_code == 200
    reply1 = resp1.json().get("reply")
    payload = _extract_ui_action_payload(reply1)
    assert payload.get("actions")[0].get("tool_name") == "RESTORE_SYSTEM_SNAPSHOT"
    assert payload.get("actions")[0].get("arguments").get("snapshot_scenario_id") == undo_id

    # 2) Approve -> should execute restore and clear undo_snapshot
    resp2 = api.post(
        "/api/v1/llm/pension-chat",
        json={
            "client_id": client_id,
            "messages": [
                {"role": "user", "content": "undo"},
                {"role": "assistant", "content": reply1},
                {"role": "user", "content": "מאשר"},
            ],
        },
    )
    assert resp2.status_code == 200

    with Session() as db:
        undo_after = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "undo_snapshot")
            .first()
        )
        assert undo_after is None
