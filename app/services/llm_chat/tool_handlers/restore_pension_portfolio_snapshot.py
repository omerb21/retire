import json

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.scenario import Scenario
from app.services.llm_chat.chat_orchestration_helpers import clear_pending_approval_request
from app.utils.llm_chat_log import get_current_request_id


def handle_restore_pension_portfolio_snapshot(
    *,
    args: dict,
    client_id: int,
    db: Session,
) -> str:
    snapshot_scenario_id = None
    safety_mode = "strict"
    if isinstance(args, dict):
        snapshot_scenario_id = args.get("snapshot_scenario_id")
        safety_mode = str(args.get("safety_mode") or "strict").strip() or "strict"

    try:
        snapshot_id_int = int(snapshot_scenario_id)
    except Exception:
        snapshot_id_int = 0

    if snapshot_id_int <= 0:
        return json.dumps(
            {
                "success": False,
                "restored_snapshot_scenario_id": None,
                "previous_snapshot_scenario_id": None,
                "message": "snapshot_scenario_id לא תקין.",
            },
            ensure_ascii=False,
        )

    source = (
        db.query(Scenario)
        .filter(Scenario.client_id == client_id)
        .filter(Scenario.scenario_name == "pension_portfolio_snapshot")
        .filter(Scenario.id == snapshot_id_int)
        .first()
    )

    if source is None or not getattr(source, "parameters", None):
        return json.dumps(
            {
                "success": False,
                "restored_snapshot_scenario_id": None,
                "previous_snapshot_scenario_id": None,
                "message": "לא נמצא snapshot_scenario_id עבור הלקוח.",
            },
            ensure_ascii=False,
        )

    latest = (
        db.query(Scenario)
        .filter(Scenario.client_id == client_id)
        .filter(Scenario.scenario_name == "pension_portfolio_snapshot")
        .order_by(Scenario.created_at.desc())
        .first()
    )
    previous_snapshot_scenario_id = int(getattr(latest, "id", 0) or 0) if latest is not None else None

    try:
        params = json.loads(source.parameters) if source.parameters else {}
    except Exception:
        params = {}
    if not isinstance(params, dict):
        params = {}

    meta = params.get("_meta")
    if not isinstance(meta, dict):
        meta = {}
    else:
        meta = dict(meta)

    trace_id = get_current_request_id() or ""
    meta["operation_type"] = "restore_snapshot"
    meta["trace_id"] = trace_id
    meta["source_snapshot_id"] = int(snapshot_id_int)
    meta["safety_mode"] = str(safety_mode)
    meta["restored_at_utc"] = datetime.now(timezone.utc).isoformat()
    params["_meta"] = meta

    scenario = Scenario(
        client_id=client_id,
        scenario_name="pension_portfolio_snapshot",
        apply_tax_planning=False,
        apply_capitalization=False,
        apply_exemption_shield=False,
        parameters=json.dumps(params, ensure_ascii=False),
    )

    try:
        db.add(scenario)
        db.commit()
        db.refresh(scenario)
        try:
            clear_pending_approval_request(db=db, client_id=client_id)
        except Exception:
            pass
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        return json.dumps(
            {
                "success": False,
                "restored_snapshot_scenario_id": None,
                "previous_snapshot_scenario_id": previous_snapshot_scenario_id,
                "message": f"שגיאה בשחזור snapshot: {str(e)}",
            },
            ensure_ascii=False,
        )

    return json.dumps(
        {
            "success": True,
            "restored_snapshot_scenario_id": int(getattr(scenario, "id", 0) or 0),
            "previous_snapshot_scenario_id": previous_snapshot_scenario_id,
            "message": "שוחזר סנאפסוט תיק בהצלחה (נוצר Scenario חדש).",
        },
        ensure_ascii=False,
    )
