import json
import re
from typing import Any

from app.schemas.llm_chat import ChatMessage


def _extract_commutation_account_number(text: str | None) -> str | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    m = re.search(r"\((\d{5,})\)", raw)
    if m:
        return str(m.group(1) or "").strip()
    # Fallback: last 5+ digit token (avoid 2000/2008)
    candidates = re.findall(r"\b(\d{5,})\b", raw)
    return str(candidates[-1]).strip() if candidates else None


def _user_wants_full_balance(text: str | None) -> bool:
    lowered = (text or "").lower()
    return ("כל" in lowered) and ("יתרה" in lowered)


def _is_target_plan_adjust_request(text: str | None) -> bool:
    lowered = (text or "").lower()
    if not lowered.strip():
        return False
    if "קצבה" not in lowered:
        return False
    if not any(
        token in lowered for token in ("גבוה", "גבוהה", "יותר", "מדי", "תקן", "לתקן")
    ):
        return False
    return True


def _infer_target_is_net_explicit(text: str | None) -> bool | None:
    lowered = (text or "").lower()
    if any(t in lowered for t in ("ברוטו", "gross", "bruto")):
        return False
    if any(t in lowered for t in ("נטו", "ביד", "אחרי מס", "net")):
        return True
    return None


def _is_target_plan_adjust_followup(
    user_text: str | None, history: list[ChatMessage]
) -> bool:
    lowered = (user_text or "").lower()
    if not lowered.strip():
        return False
    if (
        ("נטו" not in lowered)
        and ("ברוטו" not in lowered)
        and ("net" not in lowered)
        and ("gross" not in lowered)
    ):
        return False
    if not any(ch.isdigit() for ch in lowered):
        return False
    last_assistant = None
    for msg in reversed(history or []):
        if getattr(msg, "role", None) == "assistant":
            last_assistant = getattr(msg, "content", "") or ""
            break
    if not last_assistant:
        return False
    probe = last_assistant
    return "ברוטו" in probe and "נטו" in probe and "כדי לתקן" in probe


def _is_system_results_request(text: str | None) -> bool:
    lowered = (text or "").strip().lower()
    if not lowered:
        return False
    if (
        any(k in lowered for k in ("בנה", "תכנית", "תוכנית", "יעד", "תכנן", "מתווה"))
        and "קצבה" in lowered
    ):
        return False
    if any(
        k in lowered for k in ("המר", "המרה", "בצע", "ביצוע", "עזיבת עבודה", "קיבוע")
    ):
        return False
    if "קצבה" not in lowered:
        return False
    if any(
        k in lowered
        for k in ("כעת", "עכשיו", "במערכת", "מסך", "תוצאות", "בפועל", 'סה"כ', "סה")
    ):
        return True
    if lowered.startswith("מה") and ("גובה" in lowered or "כמה" in lowered):
        return True
    return False


def _format_system_results_from_cashflow(tool_result: str) -> str:
    try:
        parsed = json.loads(tool_result)
    except Exception:
        return tool_result

    if not isinstance(parsed, dict):
        return tool_result

    def _num(v: Any) -> float | None:
        try:
            if v is None:
                return None
            return float(v)
        except Exception:
            return None

    gross = _num(parsed.get("projected_pension"))
    net = _num(parsed.get("projected_pension_net"))
    tax = _num(parsed.get("monthly_tax_deduction"))
    liquid = _num(parsed.get("total_liquid_capital"))
    retire_date = str(parsed.get("retirement_date") or "").strip()
    retire_age = parsed.get("retirement_age")
    exempt_monthly = _num(parsed.get("exempt_pension_monthly"))
    exemption_pct = _num(parsed.get("exemption_percentage"))

    lines: list[str] = []
    lines.append("תוצאות בפועל במערכת – סיכום קצבה")
    if retire_date:
        lines.append(f"תאריך פרישה שנבדק: {retire_date}")
    if retire_age is not None:
        try:
            lines.append(f"גיל בפרישה: {int(retire_age)}")
        except Exception:
            pass
    if gross is not None:
        lines.append(f"קצבה ברוטו: {gross:,.2f} ₪/חודש")
    if tax is not None:
        lines.append(f"ניכוי מס חודשי משוער: {tax:,.2f} ₪")
    if net is not None:
        lines.append(f"קצבה נטו משוערת (אחרי מס הכנסה בלבד): {net:,.2f} ₪/חודש")
    if (exemption_pct is not None) or (exempt_monthly is not None):
        pct_str = f"{exemption_pct:.1f}%" if exemption_pct is not None else "לא ידוע"
        exempt_str = (
            f"{exempt_monthly:,.2f} ₪" if exempt_monthly is not None else "לא ידוע"
        )
        lines.append(
            f"פטור מקיבוע זכויות שהוחל: {pct_str} | קצבה פטורה חודשית: {exempt_str}"
        )
    if liquid is not None:
        lines.append(f"הון נזיל זמין במערכת: {liquid:,.2f} ₪")

    lines.append("")
    lines.append(
        "הערה: התשובה נבנתה ישירות מתוצאות החישוב של המערכת (ללא חישוב פנימי של הסוכן)."
    )
    return "\n".join(lines).strip()


def _fmt_money(v: object) -> str:
    try:
        if v is None:
            return "0"
        return f"{float(v):,.0f}"
    except Exception:
        return "0"


def _is_system_inventory_request(text: str | None) -> bool:
    lowered = (text or "").strip().lower()
    if not lowered:
        return False
    if any(
        k in lowered
        for k in (
            "מה יש",
            "תציג",
            "הצג",
            "פירוט",
            "פרט",
            "רשימה",
            "inventory",
            "snapshot",
        )
    ) and any(k in lowered for k in ("במערכת", "בפועל", "מסך", "נתונים")):
        return True
    if "כל האלמנטים" in lowered or "כל הנתונים" in lowered:
        return True
    return False


def _first_name(items: Any, *fields: str) -> str | None:
    if not isinstance(items, list) or not items:
        return None
    first = items[0]
    if not isinstance(first, dict):
        return None
    for f in fields:
        val = first.get(f)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def _last_assistant_message_text(messages: list[ChatMessage]) -> str:
    for msg in reversed(messages or []):
        if getattr(msg, "role", None) == "assistant":
            return getattr(msg, "content", "") or ""
    return ""


def _item_to_dict(item: Any) -> dict:
    if isinstance(item, dict):
        return item
    model_dump = getattr(item, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        return dumped if isinstance(dumped, dict) else {}
    raw = getattr(item, "__dict__", {})
    return raw if isinstance(raw, dict) else {}


def _digits_only(value: str | None) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())


def _is_ignore_blocked_text(text: str) -> bool:
    lowered = (text or "").lower()
    return any(
        token in lowered
        for token in (
            "התעלם",
            "להתעלם",
            "דלג",
            "לדלג",
            "המשך",
            "להמשיך",
            "בלי",
        )
    ) and any(
        token in lowered
        for token in (
            "חסומ",
            "פיצויים מעסיק נוכחי",
            "מעסיק נוכחי",
            "רצף זכויות",
            "שלא עברו התחשבנות",
            "התחשבנות",
        )
    )


def _user_requested_target_pension_plan(text: str) -> bool:
    lowered = (text or "").lower().replace(",", "")
    if not lowered.strip():
        return False
    planning_keywords = [
        "יעד קצבה",
        "תכנית",
        "תוכנית",
        "מתווה",
        "בנה",
        "צור",
        "תכנן",
        "תכנון",
        "build_target_pension_plan",
    ]
    if not any(k in lowered for k in planning_keywords):
        return False
    has_numeric = (
        bool(re.search(r"\b\d{2,3}\s*[kK]\b", lowered))
        or bool(re.search(r"\b\d{4,6}\b", lowered))
        or ("אלף" in lowered)
    )
    return has_numeric


def _extract_target_monthly_pension(text: str) -> float | None:
    if not isinstance(text, str) or not text.strip():
        return None
    cleaned = text.replace(",", "")

    m_k = re.search(r"\b(\d{2,3})\s*[kK]\b", cleaned)
    if m_k:
        try:
            return float(int(m_k.group(1)) * 1000)
        except Exception:
            return None

    m_num = re.search(r"\b(\d{4,6})\b", cleaned)
    if m_num:
        try:
            return float(int(m_num.group(1)))
        except Exception:
            return None

    m_he = re.search(r"\b(\d{1,3})\s*אלף\b", cleaned)
    if m_he:
        try:
            return float(int(m_he.group(1)) * 1000)
        except Exception:
            return None

    return None


def _infer_target_is_net(text: str) -> bool:
    lowered = (text or "").lower()
    if any(t in lowered for t in ("ברוטו", "gross", "bruto")):
        return False
    if any(t in lowered for t in ("נטו", "ביד", "אחרי מס", "net")):
        return True
    return False
