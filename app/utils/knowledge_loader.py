from __future__ import annotations

from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def get_retirement_kb_for_stream() -> str:
    repo_root = Path(__file__).resolve().parents[2]
    kb_dir = repo_root / "MD" / "docs" / "knowledge"

    kb_files = [
        "retirement_process_overview.md",
        "rights_fixation_basics.md",
        "severance_and_employer_exit.md",
        "scenarios_how_to_read.md",
        "no_tools_mode_guidelines.md",
        "execution_only_mode_guidelines.md",
    ]

    parts: list[str] = []
    for name in kb_files:
        p = kb_dir / name
        if not p.exists():
            continue
        txt = (p.read_text(encoding="utf-8") or "").strip()
        if not txt:
            continue
        parts.append(f"## {name}\n\n{txt}")

    combined = "\n\n".join(parts).strip()
    if not combined:
        return ""

    return "###RAG_RETIREMENT_KB###\n" + combined + "\n###END_RAG_RETIREMENT_KB###"
