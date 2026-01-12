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


def extract_inline_tool_output_blocks(text: str | None) -> list[str]:
    if not isinstance(text, str) or not text:
        return []

    markers = (
        "🔧 **פלט כלי",
        "🔧 פלט כלי",
        "Tool Result (",
        "פלט כלי (",
    )

    lines = text.splitlines()
    blocks: list[str] = []
    current: list[str] = []
    in_block = False
    empty_streak = 0

    for line in lines:
        is_marker_line = any(m in line for m in markers)

        if is_marker_line:
            if in_block and current:
                block_text = "\n".join(current).strip("\n")
                if block_text.strip():
                    blocks.append(block_text)
            in_block = True
            current = [line]
            empty_streak = 0
            continue

        if not in_block:
            continue

        current.append(line)
        if not (line or "").strip():
            empty_streak += 1
        else:
            empty_streak = 0

        if empty_streak >= 2:
            block_text = "\n".join(current).strip("\n")
            if block_text.strip():
                blocks.append(block_text)
            in_block = False
            current = []
            empty_streak = 0

    if in_block and current:
        block_text = "\n".join(current).strip("\n")
        if block_text.strip():
            blocks.append(block_text)

    return blocks


_TR_BLOCK_HEADERS = ("###TRANSPARENCY_LOG###", "###RISK_REVIEW###")


def _scrub_digits_to_provided(text: str) -> str:
    if not text:
        return text
    out = re.sub(r"\d[\d,./:%-]*", "provided", text)
    out = re.sub(r"\d", "", out)
    return out


def sanitize_transparency_and_risk_blocks(text: str | None) -> str | None:
    if not isinstance(text, str) or not text:
        return text

    lines = text.splitlines()
    out_lines: list[str] = []
    in_block = False
    empty_streak = 0

    for line in lines:
        is_header = any(line.startswith(h) for h in _TR_BLOCK_HEADERS)
        is_other_block = (line.startswith("###") and not is_header)

        if is_header:
            in_block = True
            empty_streak = 0
            header = next(h for h in _TR_BLOCK_HEADERS if line.startswith(h))
            rest = line[len(header) :]
            out_lines.append(header + _scrub_digits_to_provided(rest))
            continue

        if in_block and is_other_block:
            in_block = False
            empty_streak = 0

        if in_block:
            scrubbed = _scrub_digits_to_provided(line)
            out_lines.append(scrubbed)
            if not (line or "").strip():
                empty_streak += 1
            else:
                empty_streak = 0
            if empty_streak >= 2:
                in_block = False
                empty_streak = 0
            continue

        out_lines.append(line)

    return "\n".join(out_lines)


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

    iso_spans: list[tuple[int, int]] = []
    try:
        for m in re.finditer(r"\b\d{4}-\d{2}-\d{2}\b", text):
            iso_spans.append((m.start(), m.end()))
        for m in re.finditer(r"\b\d{4}-\d{2}\b", text):
            iso_spans.append((m.start(), m.end()))
    except Exception:
        iso_spans = []

    tokens: set[str] = set()
    for m in _NUM_TOKEN_RE.finditer(text):
        if iso_spans and any(m.start() < e and m.end() > s for (s, e) in iso_spans):
            continue
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

    violations: list[str] = []
    for t in reply_tokens:
        if t in allowed_tokens:
            continue
        if t[:1] in {"-", "+"} and (t[1:] in allowed_tokens):
            continue
        violations.append(t)
    violations = sorted(violations)
    if not violations:
        return None

    return NumericProvenanceViolation(tokens=tuple(violations))
