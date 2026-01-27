import json

from sqlalchemy.orm import Session

from app.models.scenario import Scenario
from app.services.llm_chat.chat_orchestration_helpers import clear_pending_approval_request
from app.services.snapshot_service import SnapshotService


def handle_restore_system_snapshot(*, args: dict, client_id: int, db: Session) -> str:
    undo_snapshot_scenario_id = None
    if isinstance(args, dict):
        undo_snapshot_scenario_id = args.get("snapshot_scenario_id")

    try:
        scenario_id_int = int(undo_snapshot_scenario_id)
    except Exception:
        scenario_id_int = 0

    if scenario_id_int <= 0:
        return json.dumps(
            {
                "success": False,
                "message": "snapshot_scenario_id לא תקין.",
            },
            ensure_ascii=False,
        )

    row = (
        db.query(Scenario)
        .filter(Scenario.client_id == client_id)
        .filter(Scenario.scenario_name == "undo_snapshot")
        .filter(Scenario.id == scenario_id_int)
        .first()
    )
    if row is None or not getattr(row, "parameters", None):
        return json.dumps(
            {
                "success": False,
                "message": "לא נמצא undo snapshot עבור הלקוח.",
            },
            ensure_ascii=False,
        )

    try:
        snapshot_payload = json.loads(row.parameters)
    except Exception:
        snapshot_payload = None

    if not isinstance(snapshot_payload, dict):
        return json.dumps(
            {
                "success": False,
                "message": "undo snapshot payload לא תקין.",
            },
            ensure_ascii=False,
        )

    try:
        result = SnapshotService(db).restore_snapshot(client_id, snapshot_payload)
    except Exception as e:
        return json.dumps(
            {
                "success": False,
                "message": f"שגיאה בשחזור מצב מערכת: {str(e)}",
            },
            ensure_ascii=False,
        )

    try:
        db.query(Scenario).filter(Scenario.client_id == client_id).filter(
            Scenario.scenario_name == "undo_snapshot"
        ).delete(synchronize_session=False)
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass

    try:
        clear_pending_approval_request(db=db, client_id=client_id)
    except Exception:
        pass

    if isinstance(result, dict):
        return json.dumps(result, ensure_ascii=False)

    return json.dumps(
        {
            "success": True,
            "message": "שוחזר מצב מערכת בהצלחה.",
        },
        ensure_ascii=False,
    )
