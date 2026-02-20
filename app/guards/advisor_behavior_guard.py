import re

STANDARD_BLOCK_MESSAGE = (
    "כדי לענות על זה בצורה נכונה נדרש חישוב מדויק במערכת הפרישה. "
    "אני יכול להסביר את העיקרון בלבד, בלי מספרים ובלי המלצה."
)


_DIGIT_RE = re.compile(r"[0-9]")

_MONEY_PERCENT_RE = re.compile(r"(?:\d\s*[₪%])|(?:[₪%]\s*\d)")
_DECIMAL_RE = re.compile(r"\d+\.\d+")
_THOUSANDS_RE = re.compile(r"\d{1,3}(?:,\d{3})+")
_COMMA_NUMBER_RE = re.compile(r"\d+,\d+")
_LONG_NUMBER_RE = re.compile(r"\d{4,}")
_ALLOWED_FORM_SECTION_RE = re.compile(r"(?:טופס|טפסי|סעיף)\s*\d{1,4}(?:[א-ת])?|\b\d{1,4}[א-ת]\b")

_FORBIDDEN_SYMBOLS: tuple[str, ...] = (
    "%",
    "₪",
)

_FORBIDDEN_HEBREW_PHRASES: tuple[str, ...] = (
    "כדאי",
    "עדיף",
    "ממליץ",
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


_ALLOWED_CASHFLOW_TARGET_GUIDANCE_RE = re.compile(
    r"^כדי לחשב תזרים פרישה אני צריך יעד הכנסה חודשי מפורש \(ברוטו או נטו\)\.\s*\n\s*\n"
    r"דוגמאות להעתקה:\s*\n"
    r"יעד נטו:\s*<מספר>\s*\n"
    r"יעד ברוטו:\s*<מספר>\s*\n\s*\n"
    r"דוגמאות מלאות:\s*\n"
    r"יעד נטו:\s*\d+\s*\n"
    r"יעד ברוטו:\s*\d+\s*$",
    flags=re.MULTILINE,
)


_ALLOWED_MISSING_AGE_GENDER_PROMPT_RE = re.compile(
    r"^כדי לחשב תזרים פרישה אני צריך לציין מין וגיל\.\s*\n"
    r"כתוב למשל:\s*\n"
    r"- גבר בן \d{2}\s*\n"
    r"- אישה בת \d{2}\s*$",
    flags=re.MULTILINE,
)


def enforce_behavioral_limits(text: str) -> tuple[bool, str]:
    """Returns (is_allowed, final_text)."""

    candidate = text or ""

    if _ALLOWED_CASHFLOW_TARGET_GUIDANCE_RE.match(candidate.strip()):
        return True, candidate

    if _ALLOWED_MISSING_AGE_GENDER_PROMPT_RE.match(candidate.strip()):
        return True, candidate

    if (
        ("🔧" in candidate)
        or ("פלט כלי" in candidate)
        or ("Tool Result (" in candidate)
        or ("###TOOL_CALL###" in candidate)
        or ("###UI_ACTION###" in candidate)
    ):
        return True, candidate

    if _DIGIT_RE.search(candidate):
        if (
            _MONEY_PERCENT_RE.search(candidate)
            or _DECIMAL_RE.search(candidate)
            or _THOUSANDS_RE.search(candidate)
            or _COMMA_NUMBER_RE.search(candidate)
        ):
            return False, STANDARD_BLOCK_MESSAGE

        allowed_spans = [(m.start(), m.end()) for m in _ALLOWED_FORM_SECTION_RE.finditer(candidate)]

        def _is_span_allowed(start: int, end: int) -> bool:
            for a_start, a_end in allowed_spans:
                if start >= a_start and end <= a_end:
                    return True
            return False

        for m in re.finditer(r"\d+", candidate):
            if not _is_span_allowed(m.start(), m.end()):
                return False, STANDARD_BLOCK_MESSAGE

        if _LONG_NUMBER_RE.search(candidate):
            for m in re.finditer(r"\d{4,}", candidate):
                if not _is_span_allowed(m.start(), m.end()):
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
