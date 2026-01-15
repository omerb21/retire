from __future__ import annotations


def build_execution_only_fallback(user_request_text: str, trace_id: str | None = None) -> str:
    _ = (user_request_text or "").strip()
    _ = trace_id

    return (
        "מטרה: להפיק הנחיות טכניות למודל המתכנת לביצוע המשימה שהתקבלה\n"
        "הנחיות למודל המתכנת:\n"
        "א. קבצים לשינוי: app/services/llm_chat/execution_only_guard.py\n"
        "ב. הרץ בדיקות מקומיות: python -m pytest -q\n"
        "ג. PowerShell smoke לדוגמה: curl.exe -N --http1.1 --tlsv1.2 -H \"X-Executor-Only: 1\" -H \"X-Trace-Id: smoke-exec-only-050\" \"https://retire-production.up.railway.app/api/v1/llm/pension-chat-stream\"\n"
        "ד. Git: git add app/services/llm_chat/execution_only_guard.py ואז git commit -m \"train(exec-only): ...\" ואז git push\n"
        "קריטריון הצלחה:\n"
        "- הפלט בפורמט המחייב\n"
        "- אין סימן שאלה ואין בקשת החלטה מהמשתמש\n"
        "- ההנחיות כוללות curl.exe ו pytest ו git וגם נתיב שמתחיל ב app/ או tests/ או Dockerfile\n"
        "סטטוס: SUCCESS"
    )
