from __future__ import annotations


def build_execution_only_fallback(user_request_text: str, trace_id: str | None = None) -> str:
    _ = (user_request_text or "").strip()
    _ = trace_id

    return (
        "מטרה: להפיק הנחיות טכניות למודל המתכנת לביצוע המשימה שהתקבלה\n"
        "הנחיות למודל המתכנת:\n"
        "א. קרא את בקשת המשתמש והגדר מהו שינוי הקוד המדויק הנדרש\n"
        "ב. אתר בקוד את נקודת הזרימה הרלוונטית והצע דיפ מינימלי\n"
        "ג. הכן פקודות הרצה לשחזור ב PowerShell כולל curl.exe עם headers נדרשים ו X-Trace-Id\n"
        "ד. הכן רשימת בדיקות: pytest -q ואז smoke בענן עם שלושה trace ids קבועים\n"
        "ה. החזר בסוף רשימת קבצים ששונו עם diffstat ופקודות git add commit push\n"
        "קריטריון הצלחה:\n"
        "- הפלט בפורמט המחייב\n"
        "- אין סימן שאלה ואין בקשת החלטה מהמשתמש\n"
        "- ההנחיות כוללות צעדים בדיקות ופקודות הרצה\n"
        "סטטוס: SUCCESS"
    )
