import re
from dataclasses import dataclass


_NUM_TOKEN_RE = re.compile(
    r"(?<![A-Za-z_])[-+]?\d[\d,]*(?:\.\d+)?%?",
    flags=re.UNICODE,
)


@dataclass(frozen=True)
class NumericProvenanceViolation:
    tokens: tuple[str, ...]


def _normalize_numeric_token(token: str) -> str:
    t = (token or "").strip()
    if not t:
        return ""
    if t.endswith("₪"):
        t = t[:-1].strip()
    if t.endswith("%"):
        t = t[:-1].strip()
    t = t.replace(",", "")

    sign = ""
    if t[:1] in {"+", "-"}:
        sign = t[:1]
        t = t[1:]
    if not t:
        return ""

    if "." in t:
        int_part, frac_part = t.split(".", 1)
        if int_part.isdigit():
            int_part = int_part.lstrip("0") or "0"
        frac_part = frac_part.rstrip("0")
        if not frac_part:
            t = int_part
        else:
            t = int_part + "." + frac_part
    else:
        if t.isdigit():
            t = t.lstrip("0") or "0"
    return sign + t


def extract_numeric_matches(text: str | None) -> list[str]:
    if not isinstance(text, str) or not text:
        return []
    return [m.group(0) for m in _NUM_TOKEN_RE.finditer(text)]


def _is_simple_list_index(*, text: str, start: int, end: int) -> bool:
    """Return True for small numeric list markers like '1)' or '2.' at start-of-line.

    This is intentionally narrow so we don't weaken the guard for substantive numbers.
    """
    if not isinstance(text, str) or not text:
        return False
    if start < 0 or end <= start or end > len(text):
        return False

    raw = (text[start:end] or "").strip()
    if not raw.isdigit():
        return False

    try:
        n = int(raw)
    except Exception:
        return False
    if n < 1 or n > 20:
        return False

    next_ch = text[end:end + 1]
    if next_ch not in {")", "."}:
        return False

    line_start = text.rfind("\n", 0, start)
    line_start = 0 if line_start < 0 else line_start + 1
    prefix = text[line_start:start]
    prefix_stripped = (prefix or "").strip()
    if prefix_stripped not in {"", "-", "*", "•"}:
        return False

    return True


def extract_numeric_tokens(text: str | None) -> set[str]:
    if not isinstance(text, str) or not text:
        return set()

    tokens: set[str] = set()
    for m in _NUM_TOKEN_RE.finditer(text):
        if _is_simple_list_index(text=text, start=m.start(), end=m.end()):
            continue
        raw = m.group(0)
        norm = _normalize_numeric_token(raw)
        if norm:
            tokens.add(norm)
    return tokens


def validate_reply_numeric_provenance(
    *,
    reply_text: str | None,
    allowed_source_texts: list[str],
) -> NumericProvenanceViolation | None:
    if not isinstance(reply_text, str) or not reply_text:
        return None

    reply_tokens = extract_numeric_tokens(reply_text)
    if not reply_tokens:
        return None

    allowed_text = "\n".join([t for t in allowed_source_texts if isinstance(t, str) and t])
    allowed_tokens = extract_numeric_tokens(allowed_text)

    violations = sorted(t for t in reply_tokens if t not in allowed_tokens)
    if not violations:
        return None

    return NumericProvenanceViolation(tokens=tuple(violations))
