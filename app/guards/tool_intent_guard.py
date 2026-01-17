import re

from app.services.llm_chat.intent_classifier import ChatIntent


_CONCEPTUAL_TRIGGERS: tuple[str, ...] = (
    "מה ההבדל",
    "מה המשמעות",
    "מה זה",
    "מה תפקיד",
    "מה התפקיד",
    "איך עובד",
    "באופן עקרוני",
    "באופן כללי",
)

_BLOCKED_INTENT_STRINGS: tuple[str, ...] = (
    "KNOWLEDGE",
    "EXPLANATION",
    "SYSTEM_ROLE",
    "GENERAL_QUESTION",
)

_EXPLICIT_TOOL_TRIGGERS: tuple[str, ...] = (
    "תחשב",
    "תחישב",
    "חישוב",
    "תריץ",
    "הרץ",
    "ניתוח",
    "תראה מספרים",
    "מספרים",
    "תזרים",
    "דוח",
    'דו"ח',
    "מסמך",
    "pdf",
)


_DIGIT_RE = re.compile(r"[0-9]")

_CONCEPTUAL_LEAK_LINE_TRIGGERS: tuple[str, ...] = (
    "בתיק שלך",
    "בתיק קיימ",
    "פיצויים",
    "קרן השתלמות",
    "עזיבת עבודה",
    "מסומנים כחסומים",
    "בדיקת מקורות",
    "לא נמצאו מקורות",
    "קיבלתי. אפשר להמשיך",
)

_CONCEPTUAL_LEAK_PREFIXES: tuple[str, ...] = (
    "מקור:",
    "מקורות:",
)

_CONCEPTUAL_FALLBACK_TEXT = (
    "קצבה היא הכנסה חודשית שוטפת לאורך זמן. הון הוא סכום שניתן למשיכה חד פעמית או למשיכות לפי צורך. "
    "הבחירה תלויה בצרכים של יציבות הכנסה מול נזילות וגמישות, ובשיקולי מס ותכנון."
)


def _conceptual_form_fallback(user_message: str) -> str:
    normalized = (user_message or "")
    normalized = normalized.replace("׳", "'").replace("״", '"').replace("“", '"').replace("”", '"')
    normalized = normalized.replace("‘", "'").replace("’", "'")
    normalized = normalized.replace("161 ד", "161ד")

    lowered = normalized.lower()
    is_161d = ("161ד" in normalized) or ("161d" in lowered) or ("טופס" in normalized and "161" in normalized)
    if is_161d:
        return (
            "טופס 161ד הוא טופס הצהרה/בחירה במסגרת קיבוע זכויות.\n"
            "הוא מרכז בצורה מסודרת את פרטי הבחירות וההחלטות לגבי אופן מימוש הזכויות בהקשר הפרישה.\n"
            "הטופס משמש בסיס תיעודי להצגת הבחירות מול רשות המסים ולעיתים גם מול המעסיק/המשלם.\n"
            "בדרך כלל הוא מוגש יחד עם מסמכים תומכים, כדי לשמור על עקביות בין הגופים המעורבים.\n"
            "זו תשובה מושגית כללית בלבד, בלי מספרים ובלי המלצה."
        )

    return (
        "זו שאלה מושגית על טופס/מסמך, והתשובה המדויקת תלויה בהקשר ובמסמכים הרלוונטיים.\n"
        "אפשר להסביר כאן רק עיקרון כללי, בלי מספרים ובלי המלצה."
    )


def _conceptual_fallback_for_user_message(user_message: str) -> str:
    normalized = (user_message or "")
    normalized = normalized.replace("׳", "'").replace("״", '"').replace("“", '"').replace("”", '"')
    normalized = normalized.replace("‘", "'").replace("’", "'")
    normalized = normalized.strip().lower()

    if (
        ("קיבוע" in normalized)
        or ("קיבוע זכויות" in normalized)
        or ("161ד" in normalized)
    ):
        return (
            "קיבוע זכויות הוא תהליך/החלטה תכנונית בתחום הפרישה שמטרתה לקבע מול רשות המסים את אופן מימוש הזכויות שנצברו.\n"
            "בפועל זה מתייחס להסדרה של פטורים והטבות מס אפשריות הקשורות לקצבה ולהמשך הדרך.\n"
            "המשמעות היא שלאחר הקיבוע, חלק מהבחירות לגבי מימוש הזכויות מוגדרות מראש בהתאם למסמכים שהוגשו.\n"
            "זו תשובה מושגית כללית בלבד, בלי מספרים ובלי המלצה."
        )

    if ("קצבה" in normalized) and ("הון" in normalized):
        return _CONCEPTUAL_FALLBACK_TEXT

    if "פיצויים" in normalized:
        return (
            "פיצויי פרישה הם רכיב כספי שנצבר במסגרת יחסי עבודה ויכול להיות ממומש בעת סיום עבודה בהתאם לכללים.\n"
            "הדילמות הכלליות סביב פיצויים קשורות לאופן המימוש, השלכות מס, ושילוב עם תכנון הפרישה הכולל.\n"
            "זו תשובה מושגית כללית בלבד, בלי מספרים ובלי המלצה."
        )

    return (
        "זו שאלה מושגית בתחום הפרישה, והתשובה המדויקת תלויה בהקשר ובמסמכים הרלוונטיים.\n"
        "אפשר להסביר כאן רק עיקרון כללי, בלי מספרים ובלי המלצה."
    )


def _is_conceptual_form_question(user_message: str) -> bool:
    normalized = (user_message or "").strip().lower()
    if not normalized:
        return False

    normalized = normalized.replace("׳", "'").replace("״", '"').replace("“", '"').replace("”", '"')
    normalized = normalized.replace("‘", "'").replace("’", "'")
    normalized = normalized.replace("161 ד", "161ד")

    if "161ד" in normalized or "161d" in normalized:
        return True

    wants_meaning = (
        ("מה זה" in normalized)
        or ("מה המשמעות" in normalized)
        or ("מה תפקיד" in normalized)
        or ("מה התפקיד" in normalized)
        or ("תפקיד" in normalized)
    )

    if ("טופס" in normalized) and wants_meaning:
        return True
    if ("סעיף" in normalized) and (("מה זה" in normalized) or ("מה המשמעות" in normalized)):
        return True
    if ("מסמך" in normalized) and (("מה זה" in normalized) or ("מה המשמעות" in normalized)):
        return True

    return False


def allow_tools_for_intent(user_message: str, detected_intent: ChatIntent) -> bool:
    candidate = (user_message or "").strip()
    lowered = candidate.lower()

    if _is_conceptual_form_question(candidate):
        return False

    if any(t in candidate for t in _CONCEPTUAL_TRIGGERS):
        return False

    try:
        if detected_intent == ChatIntent.NO_TOOLS:
            return False
    except Exception:
        pass

    intent_value: str | None = None
    try:
        intent_value = str(getattr(detected_intent, "value", ""))
    except Exception:
        intent_value = None

    if intent_value:
        upper = intent_value.upper()
        if upper in _BLOCKED_INTENT_STRINGS:
            return False

    if any(t.lower() in lowered for t in _EXPLICIT_TOOL_TRIGGERS):
        return True

    return True


def get_tools_disabled_reason(user_message: str, detected_intent: ChatIntent) -> str | None:
    candidate = (user_message or "").strip()

    if _is_conceptual_form_question(candidate):
        return "conceptual_form"

    if any(t in candidate for t in _CONCEPTUAL_TRIGGERS):
        return "conceptual"

    intent_value: str | None = None
    try:
        intent_value = str(getattr(detected_intent, "value", ""))
    except Exception:
        intent_value = None

    if intent_value:
        upper = intent_value.upper()
        if upper in _BLOCKED_INTENT_STRINGS:
            return "conceptual"

    return None


def sanitize_words_only_conceptual(text: str, user_message: str = "") -> str:
    conceptual_form_request = _is_conceptual_form_question(user_message)

    if not isinstance(text, str) or not text:
        if conceptual_form_request:
            return _conceptual_form_fallback(user_message)
        return _conceptual_fallback_for_user_message(user_message)

    raw_lines_initial = (text or "").splitlines()
    filtered_lines: list[str] = []
    in_ui_action_block = False
    for line in raw_lines_initial:
        stripped = (line or "").strip()
        if "###UI_ACTION###" in stripped:
            if "###END_UI_ACTION###" in stripped:
                # Single-line UI action block
                continue
            in_ui_action_block = True
            continue
        if "###END_UI_ACTION###" in stripped:
            in_ui_action_block = False
            continue
        if in_ui_action_block:
            continue
        filtered_lines.append(line)

    text = "\n".join(filtered_lines)

    raw_lines = (text or "").splitlines()
    out_lines: list[str] = []
    removed_any = False

    for line in raw_lines:
        stripped = (line or "").strip()

        if any(phrase in stripped for phrase in _CONCEPTUAL_LEAK_LINE_TRIGGERS):
            removed_any = True
            continue

        if any(stripped.startswith(prefix) for prefix in _CONCEPTUAL_LEAK_PREFIXES):
            removed_any = True
            continue

        out_lines.append(line)

    cleaned = "\n".join(out_lines)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = cleaned.strip()

    paragraphs = [p.strip() for p in cleaned.split("\n\n") if p.strip()]
    word_count = len(re.findall(r"\S+", cleaned))

    if conceptual_form_request:
        if ("161ד" in cleaned) or ("טופס" in cleaned):
            return cleaned
        return _conceptual_form_fallback(user_message)

    if removed_any and (
        (len(paragraphs) < 1)
        or ((len(cleaned) < 80) and (word_count < 8))
    ):
        return _conceptual_fallback_for_user_message(user_message)

    return cleaned


def sanitize_words_only_output(text: str) -> str:
    if not isinstance(text, str) or not text:
        return text

    raw_lines = (text or "").splitlines()
    out_lines: list[str] = []

    in_tool_block = False
    for line in raw_lines:
        stripped = line.strip()

        if stripped.startswith("###TRANSPARENCY_LOG###"):
            continue
        if stripped.startswith("###RISK_REVIEW###"):
            continue
        if stripped.startswith("###TOOL_CALL###"):
            continue
        if stripped.startswith("###UI_ACTION###") or stripped.startswith("###END_UI_ACTION###"):
            continue

        if stripped.startswith("```"):
            in_tool_block = not in_tool_block
            continue
        if in_tool_block:
            continue

        if stripped.startswith("🔧"):
            continue
        if "פלט כלי" in stripped:
            continue
        if stripped.startswith("סטטוס:"):
            continue
        if "הפקתי מהמערכת" in stripped:
            continue
        if stripped.lower().startswith("open_path"):
            continue
        if stripped.lower().startswith("report"):
            continue

        out_lines.append(line)

    cleaned = "\n".join(out_lines)

    cleaned = cleaned.replace("₪", "")
    cleaned = cleaned.replace("%", "")

    cleaned = _DIGIT_RE.sub("", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    return cleaned.strip()
