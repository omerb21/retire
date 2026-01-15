from __future__ import annotations

from enum import Enum


class ChatIntent(str, Enum):
    NO_TOOLS = "no_tools"
    REPORT = "report"
    ANALYSIS = "analysis"


_NO_TOOLS_TRIGGERS: tuple[str, ...] = (
    "בלי כלים",
    "בלי להשתמש בכלי",
    "אל תפעיל כלים",
    "אין להריץ שום כלי",
    "רק במילים",
    "במילים בלבד",
    "רק הסבר",
)

_REPORT_TRIGGERS: tuple[str, ...] = (
    "דוח",
    "דו\"ח",
    "מסמך",
    "pdf",
)


def detect_intent(last_user_message: str | None) -> ChatIntent:
    msg = (last_user_message or "").strip().lower()

    if any(t in msg for t in _NO_TOOLS_TRIGGERS):
        return ChatIntent.NO_TOOLS

    if any(t in msg for t in _REPORT_TRIGGERS):
        return ChatIntent.REPORT

    return ChatIntent.ANALYSIS


def get_stream_system_prompt_for_intent(intent: ChatIntent) -> str | None:
    if intent == ChatIntent.NO_TOOLS:
        return (
            "מצב: NO_TOOLS. המשתמש ביקש במפורש לא להפעיל כלים. "
            "אסור להחזיר TOOL_CALL. אסור לבצע חישובים או להציג מספרים שאינם מתוך פלט מערכת. "
            "החזר תשובה מילולית בלבד בעברית פשוטה וסיים בשאלה אחת בלבד."
        )

    if intent == ChatIntent.ANALYSIS:
        return (
            "מצב: ANALYSIS. מותר להפעיל כלים רק כאשר זה נדרש כדי לענות על הבקשה. "
            "אם אתה עומד להפעיל כלי, החזר אך ורק את הבלוקים: ###TRANSPARENCY_LOG###, ###RISK_REVIEW###, ###TOOL_CALL### "
            "ללא טקסט נוסף."
        )

    return None
