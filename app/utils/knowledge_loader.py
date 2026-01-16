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
        "explaining_cashflow_in_words.md",
        "blocked_compensation_explainer.md",
        "rights_fixation_in_words.md",
        "capital_vs_pension_no_numbers.md",
        "clearinghouse_data_loading_faq.md",
        "summary_report_faq.md",
        "early_retirement_overview.md",
        "pension_types_map.md",
        "tax_basics_no_numbers.md",
        "fixation_common_mistakes.md",
        "how_to_prepare_for_meeting.md",
        "post_retirement_checklist.md",
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

    return "ידע מקצועי לפרישה (לשימוש פנימי בלבד):\n\n" + combined
