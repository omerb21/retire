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
    t = t.replace(",", "")
    return t


def extract_numeric_tokens(text: str | None) -> set[str]:
    if not isinstance(text, str) or not text:
        return set()

    tokens: set[str] = set()
    for m in _NUM_TOKEN_RE.finditer(text):
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
