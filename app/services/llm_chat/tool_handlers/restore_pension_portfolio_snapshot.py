import json

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.scenario import Scenario
from app.services.pension_portfolio.snapshot_loader import (
    dedupe_pension_portfolio_snapshot,
    upsert_snapshot,
)
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
        .order_by(Scenario.id.desc())
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

    try:
        portfolio = params.get("pension_portfolio")
        if not isinstance(portfolio, list):
            portfolio = []

        scenario = upsert_snapshot(
            db,
            client_id,
            portfolio,
            meta=meta,
        )
        kept_snapshot_id, _deleted_ids = dedupe_pension_portfolio_snapshot(db, client_id)
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
            "restored_snapshot_scenario_id": int(
                kept_snapshot_id or getattr(scenario, "id", 0) or 0
            ),
            "previous_snapshot_scenario_id": previous_snapshot_scenario_id,
            "message": "שוחזר סנאפסוט תיק בהצלחה.",
        },
        ensure_ascii=False,
    )
