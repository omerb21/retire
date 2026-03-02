from fastapi.responses import StreamingResponse

from app.services.llm_chat.chat_orchestration_helpers import (
    build_approval_request_ui_action,
    load_undo_snapshot,
    store_pending_approval_request,
)
from app.services.llm_chat.message_utils import is_undo_intent_text


def _maybe_handle_undo_snapshot_approval_request(
    *, request, db, original_user_msg: str
):
    if not (
        request.client_id is not None
        and is_undo_intent_text(original_user_msg)
        and (not str(original_user_msg or "").strip().startswith("###USER_APPROVED###"))
        and (
            not str(original_user_msg or "").strip().startswith("###USER_CANCELLED###")
        )
    ):
        return None

    undo = None
    try:
        undo = load_undo_snapshot(db=db, client_id=request.client_id)
    except Exception:
        undo = None
    if undo is None:
        return StreamingResponse(
            iter(["לא נמצא מצב קודם לשחזור/ביטול. לא בוצע שינוי במערכת."]),
            media_type="text/plain",
        )

    undo_snapshot_id, _undo_payload = undo
    tool_args = {"snapshot_scenario_id": int(undo_snapshot_id)}
    ui_action = build_approval_request_ui_action(
        tool_name="RESTORE_SYSTEM_SNAPSHOT",
        tool_args=tool_args,
        reason="שחזור מצב קודם ידרוס שינויים אחרונים. נדרש אישור.",
        risk_level="high",
        rag_sources=None,
    )
    try:
        store_pending_approval_request(
            db=db,
            client_id=request.client_id,
            tool_name="RESTORE_SYSTEM_SNAPSHOT",
            tool_args=tool_args,
        )
    except Exception:
        pass
    return StreamingResponse(iter([ui_action]), media_type="text/plain")
