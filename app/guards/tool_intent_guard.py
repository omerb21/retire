import re

from app.services.llm_chat.intent_classifier import ChatIntent


_CONCEPTUAL_TRIGGERS: tuple[str, ...] = (
    "מה ההבדל",
    "מה המשמעות",
    "מה זה",
    "מה תפקיד",
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


def allow_tools_for_intent(user_message: str, detected_intent: ChatIntent) -> bool:
    candidate = (user_message or "").strip()
    lowered = candidate.lower()

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


def sanitize_words_only_conceptual(text: str) -> str:
    if not isinstance(text, str) or not text:
        return _CONCEPTUAL_FALLBACK_TEXT

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
    if removed_any and (
        (len(paragraphs) < 1)
        or ((len(cleaned) < 80) and (word_count < 8))
    ):
        return _CONCEPTUAL_FALLBACK_TEXT

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
