from fastapi.responses import StreamingResponse

from app.models.scenario import Scenario
from app.services.llm_chat.chat_orchestration_helpers import (
    build_approval_request_ui_action,
)


def _maybe_handle_restore_snapshot_approval_request(
    *,
    request,
    db,
    original_user_msg: str,
    store_pending_approval_request,
    is_no_tools_request,
):
    if not (
        request.client_id is not None
        and isinstance(original_user_msg, str)
        and original_user_msg.strip()
        and (not is_no_tools_request(original_user_msg))
    ):
        return None

    candidate = original_user_msg.strip()
    wants_restore_snapshot = any(
        phrase in candidate
        for phrase in (
            "שחזר תיק",
            "שחזר סנאפסוט",
            "החזר מצב קודם",
            "חזור לסנאפסוט מלא",
        )
    )
    if not wants_restore_snapshot:
        return None

    selected_snapshot_id: int | None = None
    try:
        snapshot = (
            db.query(Scenario)
            .filter(Scenario.client_id == request.client_id)
            .filter(Scenario.scenario_name == "pension_portfolio_snapshot")
            .order_by(Scenario.id.desc())
            .first()
        )
    except Exception:
        snapshot = None

    if snapshot is None:
        return StreamingResponse(
            iter(
                ["לא נמצא סנאפסוט תיק לשחזור. אנא העלה/שמור תיק פנסיוני ואז נסה שוב."]
            ),
            media_type="text/plain",
        )

    try:
        selected_snapshot_id = int(getattr(snapshot, "id", 0) or 0)
    except Exception:
        selected_snapshot_id = 0

    if not selected_snapshot_id or selected_snapshot_id <= 0:
        return StreamingResponse(
            iter(["לא הצלחתי לזהות סנאפסוט תיק לשחזור."]),
            media_type="text/plain",
        )

    tool_args = {
        "snapshot_scenario_id": int(selected_snapshot_id),
        "safety_mode": "strict",
    }
    ui_action = build_approval_request_ui_action(
        tool_name="RESTORE_PENSION_PORTFOLIO_SNAPSHOT",
        tool_args=tool_args,
        reason="שחזור תיק לסנאפסוט קודם עלול לדרוס מצב אחרי המרות. נדרש אישור.",
        risk_level="high",
        rag_sources=None,
    )
    try:
        store_pending_approval_request(
            db=db,
            client_id=request.client_id,
            tool_name="RESTORE_PENSION_PORTFOLIO_SNAPSHOT",
            tool_args=tool_args,
        )
    except Exception:
        pass
    return StreamingResponse(iter([ui_action]), media_type="text/plain")
