from __future__ import annotations

from enum import Enum


class ChatIntent(str, Enum):
    NO_TOOLS = "no_tools"
    REPORT = "report"
    ANALYSIS = "analysis"


_STREAM_BASE_SYSTEM_PROMPT = (
    "אתה פועל אך ורק במסגרת endpoint: /api/v1/llm/pension-chat-stream.\n"
    "ה-stream חייב לפעול תמיד לפי מצב אחד בלבד מתוך שלושה (ללא ערבוב): NO_TOOLS / REPORT / ANALYSIS.\n\n"
    "NO_TOOLS:\n"
    "- אסור להפעיל כלים ואסור להחזיר ###TOOL_CALL###.\n"
    "- תשובה בעברית בלבד, רק במילים, ללא מספרים.\n\n"
    "REPORT:\n"
    "- אסור לכתוב דוח בטקסט.\n"
    "- אסור להחזיר ###TOOL_CALL###.\n"
    "- חובה להחזיר ###UI_ACTION###...###END_UI_ACTION### בלבד.\n"
    "- חריג C: אם מדובר ב-QA או 'בדיקת מערכת', מותר להוסיף אחרי ה-UI_ACTION רק שורה אחת בדיוק:\n"
    "PASS - סיכום QA סופי לאחר יצירת הדוח\n"
    "- בלי מספרים.\n\n"
    "ANALYSIS:\n"
    "- מותר להפעיל כלים.\n"
    "- אם הופעל כלי והוזרם '🔧 פלט כלי', חובה לסיים מיד לאחר מכן במשפט קצר בעברית בלי מספרים (stop-after-tool).\n"
    "- כל מספר/תוצאה פיננסית חייבים להגיע רק מפלט כלי/מערכת; אין לבצע חישובים עצמאיים.\n"
)


_NO_TOOLS_TRIGGERS: tuple[str, ...] = (
    "אל תפעיל כלים",
    "בלי כלים",
    "רק במילים",
    "במילים בלבד",
    "בלי מספרים",
)

_REPORT_TRIGGERS: tuple[str, ...] = (
    "דוח",
    "דו\"ח",
    "מסמך",
    "מסמכים",
    "הפקת דוח",
    "שלח דוח",
    "pdf",
)

_REPORT_QA_TRIGGERS: tuple[str, ...] = (
    "qa",
    "בדיקת מערכת",
)


def detect_intent(last_user_message: str | None) -> ChatIntent:
    msg = (last_user_message or "").strip().lower()
    msg = msg.replace("״", '"').replace("׳", "'")

    if any(t in msg for t in _NO_TOOLS_TRIGGERS):
        return ChatIntent.NO_TOOLS

    if any(t in msg for t in _REPORT_TRIGGERS):
        return ChatIntent.REPORT

    return ChatIntent.ANALYSIS


def report_requires_qa_line(last_user_message: str | None) -> bool:
    msg = (last_user_message or "").strip().lower()
    if not msg:
        return False
    return any(t.lower() in msg for t in _REPORT_QA_TRIGGERS)


def get_stream_base_system_prompt() -> str:
    return _STREAM_BASE_SYSTEM_PROMPT


def get_stream_system_prompt(intent: ChatIntent) -> str:
    if intent == ChatIntent.NO_TOOLS:
        return (
            "מצב: NO_TOOLS. אסור להחזיר TOOL_CALL. אסור להציג מספרים. "
            "ענה בעברית בקצרה ובמילים בלבד."
        )

    if intent == ChatIntent.REPORT:
        return (
            "מצב: REPORT. אל תכתוב דוח ואל תציע צעדים. "
            "יש להפיק דוח דרך כלי ולהחזיר רק ###UI_ACTION###...###END_UI_ACTION###."
        )

    return (
        "מצב: ANALYSIS. מותר להפעיל כלים. "
        "אם מפעילים כלי, החזר אך ורק: ###TRANSPARENCY_LOG###, ###RISK_REVIEW###, ###TOOL_CALL### ללא טקסט נוסף."
    )


def get_stream_system_prompt_for_intent(intent: ChatIntent) -> str | None:
    return get_stream_system_prompt(intent)
