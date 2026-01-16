import re

STANDARD_BLOCK_MESSAGE = (
    "כדי לענות על זה בצורה נכונה נדרש חישוב מדויק במערכת הפרישה. "
    "אני יכול להסביר את העיקרון בלבד, בלי מספרים ובלי המלצה."
)


_DIGIT_RE = re.compile(r"[0-9]")

_FORBIDDEN_SYMBOLS: tuple[str, ...] = (
    "%",
    "₪",
)

_FORBIDDEN_HEBREW_PHRASES: tuple[str, ...] = (
    "כדאי",
    "עדיף",
    "ממליץ",
    "מומלץ",
    "חייב",
    "בוודאות",
    "נכון יותר",
    "עדיף לבחור",
)

_FORBIDDEN_DECISION_PHRASES: tuple[str, ...] = (
    "מה עדיף",
    "הבחירה הנכונה",
    "עדיף כך",
)

# Explicit bypass attempts
_FORBIDDEN_BYPASS_PHRASES: tuple[str, ...] = (
    "עזוב מערכת",
    "תגיד בערך",
    "בערך",
)

_FORBIDDEN_PERCENT_WORDS: tuple[str, ...] = (
    "אחוז",
    "אחוזים",
)


def enforce_behavioral_limits(text: str) -> tuple[bool, str]:
    """Returns (is_allowed, final_text)."""

    candidate = text or ""

    if _DIGIT_RE.search(candidate):
        return False, STANDARD_BLOCK_MESSAGE

    if any(sym in candidate for sym in _FORBIDDEN_SYMBOLS):
        return False, STANDARD_BLOCK_MESSAGE

    if any(word in candidate for word in _FORBIDDEN_PERCENT_WORDS):
        return False, STANDARD_BLOCK_MESSAGE

    if any(phrase in candidate for phrase in _FORBIDDEN_HEBREW_PHRASES):
        return False, STANDARD_BLOCK_MESSAGE

    if any(phrase in candidate for phrase in _FORBIDDEN_DECISION_PHRASES):
        return False, STANDARD_BLOCK_MESSAGE

    if any(phrase in candidate for phrase in _FORBIDDEN_BYPASS_PHRASES):
        return False, STANDARD_BLOCK_MESSAGE

    return True, candidate
