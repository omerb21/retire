from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import NamedTuple


class _KnowledgeSource(NamedTuple):
    name: str
    keywords: tuple[str, ...]
    relative_path_parts: tuple[str, ...]
    window_lines: int
    max_chars: int


_DOC_SOURCES: tuple[_KnowledgeSource, ...] = (
    _KnowledgeSource(
        name="tax_spread_logic",
        keywords=("פריסת מס", "tax_spread", "פריסה", "spread"),
        relative_path_parts=("MD", "docs", "TAX_SPREAD_LOGIC.md"),
        window_lines=50,
        max_chars=2600,
    ),
    _KnowledgeSource(
        name="validation_rules",
        keywords=("תיקוף", "ולידציה", "validation", "מספר זהות", "תעודת זהות", "birth date"),
        relative_path_parts=("MD", "docs", "validation_rules.md"),
        window_lines=45,
        max_chars=2400,
    ),
    _KnowledgeSource(
        name="pension_calculation_features",
        keywords=("indexation", "cpi", "הצמדה", "indexation_method"),
        relative_path_parts=("MD", "docs", "pension_calculation_features.md"),
        window_lines=40,
        max_chars=2200,
    ),
    _KnowledgeSource(
        name="agent_playbooks",
        keywords=(
            "playbook",
            "נטו",
            "אחרי מס",
            "קיבוע זכויות",
            "פטור מקסימלי",
            "RUN_RETIREMENT_CASHFLOW_ANALYSIS",
            "GET_TAX_PROJECTION",
        ),
        relative_path_parts=("MD", "docs", "agent_playbooks.md"),
        window_lines=60,
        max_chars=2800,
    ),
    _KnowledgeSource(
        name="agent_tools_catalog",
        keywords=(
            "כלי",
            "tools",
            "RUN_RETIREMENT_CASHFLOW_ANALYSIS",
            "GET_TAX_PROJECTION",
            "GENERATE_FULL_REPORT",
            "TRANSFORM_FUNDS_TO_ASSETS",
        ),
        relative_path_parts=("MD", "docs", "agent_tools_catalog.md"),
        window_lines=55,
        max_chars=2600,
    ),
)


def build_knowledge_system_message(user_message: str) -> str | None:
    if not user_message:
        return None

    lowered = user_message.lower()
    scored: list[tuple[int, int, _KnowledgeSource]] = []
    for idx, src in enumerate(_DOC_SOURCES):
        score = sum(1 for k in src.keywords if k and k.lower() in lowered)
        if score > 0:
            scored.append((score, -idx, src))

    matched = [t[2] for t in sorted(scored, reverse=True)]

    if not matched:
        return None

    excerpts: list[str] = []
    for src in matched[:2]:
        excerpt = _read_doc_excerpt(
            tuple(src.relative_path_parts),
            keywords=src.keywords,
            window_lines=src.window_lines,
            max_chars=src.max_chars,
        )
        if excerpt:
            excerpts.append(f"מקור: {src.relative_path_parts[-1]}\n{excerpt}")

    if not excerpts:
        return None

    joined = "\n\n---\n\n".join(excerpts)
    return (
        "ידע מערכת רלוונטי (להקשר בלבד):\n"
        "- השתמש בזה להסברים ולדיוק מושגים.\n"
        "- עבור מספרים/תוצאות כספיות, השתמש רק בנתוני לקוח וכלים.\n\n"
        f"{joined}"
    )


def _repo_root_from_here() -> Path:
    return Path(__file__).resolve().parents[3]


@lru_cache(maxsize=64)
def _read_doc_lines(relative_path_parts: tuple[str, ...]) -> list[str]:
    root = _repo_root_from_here()
    path = root.joinpath(*relative_path_parts)
    if not path.exists() or not path.is_file():
        return []

    try:
        content = path.read_text(encoding="utf-8")
    except Exception:
        return []

    return content.splitlines()


def _read_doc_excerpt(
    relative_path_parts: tuple[str, ...],
    *,
    keywords: tuple[str, ...],
    window_lines: int,
    max_chars: int,
) -> str:
    lines = _read_doc_lines(relative_path_parts)
    if not lines:
        return ""

    window = window_lines if window_lines > 0 else 40
    half_window = max(10, window // 2)

    # Find first match line
    match_idx: int | None = None
    lowered_lines = [ln.lower() for ln in lines]
    lowered_keywords = [k.lower() for k in keywords if k]
    for i, ln in enumerate(lowered_lines):
        if any(k in ln for k in lowered_keywords):
            match_idx = i
            break

    if match_idx is None:
        start = 0
        end = min(len(lines), window)
    else:
        start = max(0, match_idx - half_window)
        end = min(len(lines), match_idx + half_window)

    excerpt = "\n".join(lines[start:end]).strip()
    if max_chars > 0 and len(excerpt) > max_chars:
        excerpt = excerpt[:max_chars].rstrip() + "…"
    return excerpt
