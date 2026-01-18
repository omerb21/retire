import re

from app.guards.advice_domain import AdviceDomain


_WORD_RE = re.compile(r"[\w\u0590-\u05FF]+", re.UNICODE)


_DOMAIN_VOCAB: set[str] = {
    "פיצויים",
    "מענק",
    "פרישה",
    "כספי",
    "סיום",
    "עבודה",
    "קיבוע",
    "זכויות",
    "טופס",
    "פטור",
    "קצבה",
    "מס",
    "מיסוי",
    "תכנון",
    "סיכון",
    "תנודתיות",
    "מניות",
    "אגח",
    "מסלול",
    "השקעה",
    "לשלם",
    "פחות",
    "מיותר",
}


def _tokenize(user_text: str) -> list[str]:
    normalized = (user_text or "").strip().lower()
    normalized = normalized.replace("״", '"').replace("׳", "'")
    raw = _WORD_RE.findall(normalized)
    tokens: list[str] = []
    for token in raw:
        if token.startswith("ה") and len(token) > 1:
            remainder = token[1:]
            if remainder in _DOMAIN_VOCAB:
                tokens.append(remainder)
                continue
        tokens.append(token)
    return tokens


def _has_phrase(tokens: list[str], phrase_tokens: tuple[str, ...]) -> bool:
    if not tokens or not phrase_tokens:
        return False
    n = len(phrase_tokens)
    if n == 1:
        return phrase_tokens[0] in set(tokens)
    for i in range(0, len(tokens) - n + 1):
        if tuple(tokens[i : i + n]) == phrase_tokens:
            return True
    return False


def resolve_advice_domain(user_text: str) -> AdviceDomain:
    tokens = _tokenize(user_text)
    if not tokens:
        return AdviceDomain.UNKNOWN

    compensation_phrases: tuple[tuple[str, ...], ...] = (
        ("פיצויים",),
        ("כספי", "פיצויים"),
        ("מענק", "פרישה"),
        ("כספי", "סיום", "עבודה"),
    )

    commutation_phrases: tuple[tuple[str, ...], ...] = (
        ("היוון",),
        ("היוון", "חלקי"),
        ("סכום", "חד", "פעמי", "מהקצבה"),
        ("הפחתת", "קצבה"),
    )

    fixation_phrases: tuple[tuple[str, ...], ...] = (
        ("קיבוע",),
        ("קיבוע", "זכויות"),
        ("טופס", "161ד"),
        ("161ד",),
        ("161d",),
        ("פטור", "קצבה"),
        ("פטור", "ממס", "על", "קצבה"),
    )

    investment_risk_phrases: tuple[tuple[str, ...], ...] = (
        ("מסלול", "השקעה"),
        ("סיכון",),
        ("תנודתיות",),
        ("מניות",),
        ("אג", "ח"),
        ("אגח",),
        ("בגיל", "פרישה"),
    )

    tax_phrases: tuple[tuple[str, ...], ...] = (
        ("מס",),
        ("מיסוי",),
        ("לשלם", "פחות", "מס"),
        ("מס", "מיותר"),
        ("תכנון", "מס"),
    )

    for phrase in compensation_phrases:
        if _has_phrase(tokens, phrase):
            return AdviceDomain.COMPENSATION

    for phrase in commutation_phrases:
        if _has_phrase(tokens, phrase):
            return AdviceDomain.COMMUTATION

    for phrase in fixation_phrases:
        if _has_phrase(tokens, phrase):
            return AdviceDomain.FIXATION

    for phrase in investment_risk_phrases:
        if _has_phrase(tokens, phrase):
            return AdviceDomain.INVESTMENT_RISK

    for phrase in tax_phrases:
        if _has_phrase(tokens, phrase):
            return AdviceDomain.TAX_OPTIMIZATION

    return AdviceDomain.UNKNOWN
