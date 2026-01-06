import json
from .chat_helpers import _first_name


def _format_system_inventory_snapshot(tool_result: str) -> str:
    try:
        parsed = json.loads(tool_result)
    except Exception:
        return tool_result

    if not isinstance(parsed, dict):
        return tool_result

    counts = parsed.get("counts") if isinstance(parsed.get("counts"), dict) else {}
    entities = parsed.get("entities") if isinstance(parsed.get("entities"), dict) else {}

    def _count(name: str) -> int:
        try:
            return int(counts.get(name) or 0)
        except Exception:
            return 0

    lines: list[str] = []
    lines.append("מצב בפועל במערכת – Snapshot (DB)")
    generated_at = str(parsed.get("generated_at") or "").strip()
    if generated_at:
        lines.append(f"נוצר בתאריך: {generated_at}")
    lines.append("")
    lines.append("סיכום ישויות:")
    lines.append(f"- קצבאות (PensionFund): {_count('pension_funds')}")
    lines.append(f"- נכסי הון (CapitalAsset): {_count('capital_assets')}")
    lines.append(f"- הכנסות נוספות (AdditionalIncome): {_count('additional_incomes')}")
    lines.append(f"- מעסיק נוכחי (CurrentEmployer): {_count('current_employers')}")
    lines.append(f"- מענקי מעסיק נוכחי (EmployerGrant): {_count('employer_grants')}")
    lines.append(f"- מענקים ממעסיקים קודמים (Grant legacy): {_count('legacy_grants')}")
    lines.append(f"- אירועי עזיבת עבודה (TerminationEvent): {_count('termination_events')}")
    lines.append(f"- קיבוע זכויות (FixationResult): {_count('fixation_results')}")
    lines.append(f"- קצבאות מערכת קיבוע ישנה (Pension): {_count('pensions')}")
    lines.append(f"- היוונים מערכת קיבוע ישנה (Commutation): {_count('commutations')}")
    lines.append(f"- תרחישים/תוצאות (Scenario): {_count('scenarios')}")

    # Provide a tiny sample of what's inside, without dumping JSON.
    sample_pf = _first_name(entities.get("pension_funds"), "fund_name")
    sample_ca = _first_name(entities.get("capital_assets"), "asset_name")
    sample_ce = _first_name(entities.get("current_employers"), "employer_name")
    if any([sample_pf, sample_ca, sample_ce]):
        lines.append("")
        lines.append("דוגמאות (פריט ראשון מכל קטגוריה, אם קיים):")
        if sample_pf:
            lines.append(f"- קצבה: {sample_pf}")
        if sample_ca:
            lines.append(f"- נכס הון: {sample_ca}")
        if sample_ce:
            lines.append(f"- מעסיק נוכחי: {sample_ce}")

    lines.append("")
    lines.append(
        "הערה: התשובה נבנתה ישירות מ-DB (Snapshot) ללא השלמות/חישובים פנימיים של הסוכן. "
        "אם תרצה פירוט של קטגוריה ספציפית (למשל 'תציג את כל נכסי ההון'), תגיד איזו קטגוריה."
    )
    return "\n".join(lines).strip()
