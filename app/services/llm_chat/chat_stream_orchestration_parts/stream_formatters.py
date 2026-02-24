import json
from typing import Any

from .chat_helpers import _fmt_money


def _format_list_all_entities(
    tool_result: str,
    *,
    effective_portfolio: Any,
    effective_snapshot_at: Any,
) -> str:
    try:
        parsed = json.loads(tool_result)
    except Exception:
        parsed = None

    entities = parsed.get("entities") if isinstance(parsed, dict) else {}
    pension_funds = (
        entities.get("pension_funds") if isinstance(entities, dict) else None
    )
    capital_assets = (
        entities.get("capital_assets") if isinstance(entities, dict) else None
    )
    additional_incomes = (
        entities.get("additional_incomes") if isinstance(entities, dict) else None
    )

    lines: list[str] = []
    lines.append("הנתונים שנמצאים כרגע במערכת (DB) + תיק מסלקה שניטען:")

    # Portfolio snapshot (Maslaka) summary
    if isinstance(effective_portfolio, list):
        lines.append("")
        lines.append("תיק פנסיוני (מסלקה / טבלת מוצרים):")
        lines.append(f"- מספר חשבונות: {len(effective_portfolio)}")
        if effective_snapshot_at:
            lines.append(f"- תאריך snapshot: {effective_snapshot_at}")

    # Additional incomes
    lines.append("")
    lines.append("הכנסות נוספות (AdditionalIncome):")
    if isinstance(additional_incomes, list) and additional_incomes:
        for ai in additional_incomes:
            if not isinstance(ai, dict):
                continue
            desc = (
                (ai.get("description") or ai.get("source_type") or "הכנסה").strip()
                if isinstance(ai.get("description") or ai.get("source_type") or "", str)
                else "הכנסה"
            )
            amount = _fmt_money(ai.get("amount"))
            freq = ai.get("frequency") or ""
            start = ai.get("start_date") or ""
            end = ai.get("end_date") or ""
            suffix = f" | תוקף: {start}–{end}" if start or end else ""
            lines.append(f"- {desc}: {amount} ₪ ({freq}){suffix}")
    else:
        lines.append("- לא נמצאו הכנסות נוספות ב-DB")

    # Pension funds
    lines.append("")
    lines.append("קצבאות / קופות (PensionFund):")
    if isinstance(pension_funds, list) and pension_funds:
        for pf in pension_funds:
            if not isinstance(pf, dict):
                continue
            name = (
                (pf.get("fund_name") or "קופה").strip()
                if isinstance(pf.get("fund_name") or "", str)
                else "קופה"
            )
            p_amount = _fmt_money(pf.get("pension_amount"))
            bal = _fmt_money(pf.get("balance"))
            lines.append(f"- {name}: קצבה={p_amount} ₪/חודש | יתרה={bal} ₪")
    else:
        lines.append(
            "- לא נמצאו קצבאות/קופות ב-DB (ייתכן שעדיין לא בוצעה המרה מהמסלקה לנכסים)"
        )

    # Capital assets
    lines.append("")
    lines.append("נכסי הון (CapitalAsset):")
    if isinstance(capital_assets, list) and capital_assets:
        for ca in capital_assets:
            if not isinstance(ca, dict):
                continue
            name = (
                (ca.get("asset_name") or "נכס").strip()
                if isinstance(ca.get("asset_name") or "", str)
                else "נכס"
            )
            cur = _fmt_money(ca.get("current_value"))
            mi = _fmt_money(ca.get("monthly_income"))
            lines.append(f"- {name}: שווי={cur} ₪ | הכנסה חודשית={mi} ₪")
    else:
        lines.append("- לא נמצאו נכסי הון ב-DB")

    lines.append("")
    lines.append(
        "אם תרצה שאציג גם את פירוט חשבונות המסלקה (9 חשבונות) לפי שם תכנית/מספר חשבון/יתרה — תגיד: 'תציג פירוט תיק מסלקה'."
    )
    return "\n".join(lines).strip()


def _format_data_awareness_snapshot(
    tool_result: str,
    *,
    effective_portfolio: Any,
    effective_snapshot_at: Any,
) -> str:
    try:
        parsed = json.loads(tool_result)
    except Exception:
        parsed = None

    counts = parsed.get("counts") if isinstance(parsed, dict) else {}

    def _count(name: str) -> int:
        try:
            return int(counts.get(name) or 0) if isinstance(counts, dict) else 0
        except Exception:
            return 0

    lines: list[str] = []
    lines.append("כן — אני עובד על בסיס הנתונים שנמצאים כרגע במערכת עבור הלקוח הזה.")

    if isinstance(effective_portfolio, list):
        lines.append("")
        lines.append("תיק פנסיוני (מסלקה / טבלת מוצרים):")
        lines.append(f"- מספר חשבונות שנטענו: {len(effective_portfolio)}")
        if effective_snapshot_at:
            lines.append(f"- תאריך snapshot אחרון: {effective_snapshot_at}")

    lines.append("")
    lines.append("מקורות/ישויות שנמצאו ב-DB:")
    lines.append(f"- קצבאות (PensionFund): {_count('pension_funds')}")
    lines.append(f"- נכסי הון (CapitalAsset): {_count('capital_assets')}")
    lines.append(f"- הכנסות נוספות (AdditionalIncome): {_count('additional_incomes')}")
    lines.append(f"- מעסיק נוכחי (CurrentEmployer): {_count('current_employers')}")

    lines.append("")
    lines.append(
        "אם תרצה לוודא *בדיוק* אילו מקורות נכללים בתזרים (למשל העסק/נכסי הון), תגיד: 'תציג לי את כל ההכנסות הנוספות' או 'תציג לי את כל נכסי ההון'."
    )
    return "\n".join(lines).strip()
