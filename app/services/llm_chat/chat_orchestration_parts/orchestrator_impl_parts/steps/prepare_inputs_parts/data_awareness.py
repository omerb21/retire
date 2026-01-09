from __future__ import annotations

import json

from app.schemas.llm_chat import ChatResponse


def _maybe_handle_data_awareness(
    *,
    request,
    db,
    request_id: str,
    original_user_msg,
    effective_portfolio,
    effective_snapshot_at,
    computed_data,
    _execute_tool_call,
) -> ChatResponse | None:
    from app.services.llm_chat.orchestration_utils import is_data_awareness_request

    if request.client_id is not None and is_data_awareness_request(original_user_msg):
        tool_result = _execute_tool_call(
            "GET_SYSTEM_STATE_SNAPSHOT",
            {},
            request.client_id,
            db,
            pension_portfolio=effective_portfolio,
            force_max_exemption=False,
            user_approved=True,
            request_id=request_id,
        )
        try:
            parsed = json.loads(tool_result)
        except Exception:
            parsed = None
        counts = parsed.get("counts") if isinstance(parsed, dict) else {}

        def _count(name: str) -> int:
            try:
                return int(counts.get(name) or 0) if isinstance(counts, dict) else 0
            except Exception:
                return 0

        lines: list[str] = []
        lines.append("כן — אני עובד על בסיס הנתונים שנמצאים כרגע במערכת עבור הלקוח הזה.")
        if isinstance(effective_portfolio, list):
            lines.append("")
            lines.append("תיק פנסיוני (מסלקה / טבלת מוצרים):")
            lines.append(f"- מספר חשבונות שנטענו: {len(effective_portfolio)}")
            if effective_snapshot_at:
                lines.append(f"- תאריך snapshot אחרון: {effective_snapshot_at}")

        lines.append("")
        lines.append("מקורות/ישויות שנמצאו ב-DB:")
        lines.append(f"- קצבאות (PensionFund): {_count('pension_funds')}")
        lines.append(f"- נכסי הון (CapitalAsset): {_count('capital_assets')}")
        lines.append(f"- הכנסות נוספות (AdditionalIncome): {_count('additional_incomes')}")
        lines.append(f"- מעסיק נוכחי (CurrentEmployer): {_count('current_employers')}")
        lines.append("")
        lines.append(
            "אם תרצה, אני יכול להציג פירוט לפי קטגוריה (למשל: 'תציג את כל ההכנסות הנוספות')."
        )
        return ChatResponse(reply="\n".join(lines).strip(), computed_data=computed_data)

    return None
