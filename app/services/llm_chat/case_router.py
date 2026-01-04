from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class CasePolicy:
    allow_llm: bool = True
    allowed_tools: None = None


@dataclass(frozen=True)
class CaseDecision:
    case_id: str
    policy: CasePolicy


def _is_explicit_write_request(text: str | None) -> bool:
    raw = str(text or "").strip().lower()
    if not raw:
        return False

    keywords = [
        "צור",
        "תיצור",
        "תצרי",
        "הוסף",
        "תוסיף",
        "תעדכן",
        "עדכן",
        "מחק",
        "תמחק",
        "שמור",
        "תשמור",
        "המר",
        "להמיר",
        "קבע",
        "תקבע",
        "בטל",
        "תבטל",
        "בצע",
        "תבצע",
        "הפק",
        "תפיק",
        "generate",
        "create",
        "update",
        "delete",
        "transform",
    ]

    for kw in keywords:
        if kw and kw in raw:
            return True

    if re.search(r"\b(יצירה|הוספה|עדכון|מחיקה|שמירה|המרה|ביטול|קיבוע)\b", raw):
        return True

    return False


def select_case(*, user_message: str | None, messages: Any, client_id: Any) -> CaseDecision:
    case_id = "interactive_write" if _is_explicit_write_request(user_message) else "interactive_readonly"
    return CaseDecision(
        case_id=case_id,
        policy=CasePolicy(allow_llm=True, allowed_tools=None),
    )
