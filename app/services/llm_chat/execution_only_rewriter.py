from __future__ import annotations


def build_exec_only_rewrite_prompt(bad_text: str, user_request_text: str) -> list[dict]:
    bad_text = (bad_text or "").strip()
    user_request_text = (user_request_text or "").strip()

    system = (
        "אתה עורך-שכתוב לפלט EXECUTION_ONLY. פלט בלבד, בלי הסברים ובלי קוד-בלוקים. "
        "שכתב את הטקסט כך שיעמוד בדיוק בכללים:\n"
        "- אין שום תו '?'\n"
        "- אין ביטויי בקשת החלטה מהמשתמש (כמו 'האם תרצה', 'בחר', 'אשר')\n"
        "- אין טקסט לפני 'מטרה:'\n"
        "- יש בדיוק 4 כותרות ובדיוק בסדר הזה:\n"
        "  1) מטרה:\n"
        "  2) אחת מהכותרות: הנחיות לביצוע: / הנחיות למודל המתכנת: / הנחיות טכניות:\n"
        "  3) קריטריון הצלחה:\n"
        "  4) סטטוס: SUCCESS\n"
        "- אין כותרות נוספות מעבר לארבע הללו\n"
        "- חובה לכלול תוכן טכני אמיתי בתוך סעיף ההנחיות: קבצים לשינוי, צעדים ממוספרים, "
        "פקודות PowerShell מוכנות להדבקה כולל curl.exe, pytest -q, git add, git commit, git push"
    )

    user = (
        "הודעת משתמש אחרונה:\n"
        f"{user_request_text}\n\n"
        "פלט שגוי לשכתוב:\n"
        f"{bad_text}\n\n"
        "החזר כעת פלט מתוקן בלבד בפורמט המחייב."
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
