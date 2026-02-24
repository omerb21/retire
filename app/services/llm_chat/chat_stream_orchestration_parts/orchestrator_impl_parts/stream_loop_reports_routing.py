import json
from typing import Any

from fastapi.responses import StreamingResponse


def _maybe_route_to_reports_page(*, request, original_user_msg: str):
    def _should_route_to_reports_page(user_msg: str) -> bool:
        lowered = (user_msg or "").strip().lower()
        if not lowered:
            return False

        # Do NOT intercept system results reports ("דוח תוצאות") or conceptual questions
        # like "איך לקרוא דוח תזרים".
        if ("תוצאות" in lowered) or ("results" in lowered):
            return False
        if ("תזרים" in lowered) or ("cashflow" in lowered):
            return False
        if (
            lowered.startswith("איך ")
            or lowered.startswith("כיצד ")
            or lowered.startswith("how ")
        ):
            return False

        # Do not intercept full report generation / QA flows.
        if ("מלא" in lowered) or ("full" in lowered) or ("qa" in lowered):
            return False

        report_verbs = ("שלח", "הפק", "צור", "תפיק", "פתח")
        has_verb = any(tok in lowered for tok in report_verbs)
        has_report_word = (
            ("דוח" in lowered)
            or ('דו"ח' in lowered)
            or ("report" in lowered)
            or ("reports" in lowered)
        )
        if not has_report_word:
            return False

        lowered_compact = lowered.strip()
        if lowered_compact in {"report", "reports"}:
            return True

        # For generic "דוח" requests we only route when it's clearly a document open request.
        wants_summary = (
            ("דוח מסכם" in lowered) or ("מסכם" in lowered) or ("summary" in lowered)
        )
        return bool(has_verb or wants_summary)

    if (
        request.client_id is not None
        and isinstance(original_user_msg, str)
        and (not original_user_msg.strip().startswith("###USER_APPROVED###"))
        and _should_route_to_reports_page(original_user_msg)
    ):
        ui_payload: dict[str, Any] = {
            "type": "ui_actions",
            "actions": [
                {
                    "type": "open_url",
                    "url": f"/clients/{request.client_id}/reports?auto_html=1",
                    "label": "פתח דוח",
                }
            ],
        }
        ui_action = (
            "###UI_ACTION###"
            + json.dumps(ui_payload, ensure_ascii=False)
            + "###END_UI_ACTION###\n"
        )
        return StreamingResponse(
            iter([ui_action, "פתחתי את הדוח בטאב חדש."]),
            media_type="text/plain",
        )

    return None
