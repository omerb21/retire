import json
from typing import Any

from fastapi.responses import StreamingResponse

from app.services.llm_chat.intent_classifier import ChatIntent


def _maybe_handle_report_intent_ui_shortcut(
    *,
    request,
    tools_enabled: bool,
    ui_action_short_circuit_allowed: bool,
    resolved_intent,
 ):
    if not (
        tools_enabled
        and ui_action_short_circuit_allowed
        and resolved_intent == ChatIntent.REPORT
        and request.client_id is not None
    ):
        return None

    actions: list[dict[str, str]] = [
        {
            "type": "open_url",
            "url": f"/clients/{request.client_id}/reports?auto_html=1",
            "label": "פתח דוח",
        }
    ]
    ui_payload: dict[str, Any] = {"type": "ui_actions", "actions": actions}
    ui_action = "###UI_ACTION###" + json.dumps(ui_payload, ensure_ascii=False) + "###END_UI_ACTION###\n"
    return StreamingResponse(
        iter([ui_action, "פתחתי את הדוח בטאב חדש."]),
        media_type="text/plain",
    )
