from __future__ import annotations

from typing import Any

from app.schemas.llm_chat import ChatResponse
from app.services.llm_chat.orchestration_utils import sanitize_user_visible_text


def _build_chat_response(
    *,
    final_reply: str,
    forced_user_prefix: str,
    is_portfolio_analysis: bool,
    qa_summary_required: bool,
    report_open_path: str | None,
    current_step: int,
    max_steps: int,
    computed_data: Any,
) -> ChatResponse:
    if current_step >= max_steps:
        final_reply += (
            "\n\n(הערה: עצרתי את רצף הפעולות האוטומטי כדי למנוע לולאה אינסופית)"
        )

    if qa_summary_required:
        lowered_final = (final_reply or "").lower()
        if ("pass" not in lowered_final) and ("fail" not in lowered_final):
            if report_open_path:
                final_reply += (
                    "\n\nFAIL - לא התקבלה תשובת QA סופית מהמודל לאחר יצירת הדוח. "
                    f"open_path: {report_open_path}"
                )
            else:
                final_reply += (
                    "\n\nFAIL - לא התקבלה תשובת QA סופית מהמודל לאחר יצירת הדוח."
                )

    return ChatResponse(
        reply=(
            (
                lambda txt: (
                    (
                        "הערה: התרחישים האוטומטיים הם הערכה ראשונית/גסה בלבד ואינם חישוב ביצוע מדויק.\n\n"
                        + txt
                    )
                    if is_portfolio_analysis
                    and isinstance(txt, str)
                    and txt.strip()
                    and (
                        "הערכה" not in txt
                        and "הערכה גסה" not in txt
                        and "ראשונית" not in txt
                    )
                    else txt
                )
            )(sanitize_user_visible_text(forced_user_prefix + final_reply))
        ),
        computed_data=computed_data,
    )
