"""Tool call helper functions (extract_*/parse_*) for chat orchestration."""

# NOTE: This module will be filled by move-only extraction from orchestration_utils.py.
# Keep bodies 1:1 when moving functions.

import json
import re
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from typing import Any

from app.services.retirement_age_service import get_retirement_date

try:
    from app.services.retirement_age_service import DEFAULT_MALE_RETIREMENT_AGE as _DEFAULT_RETIREMENT_AGE_FALLBACK
except Exception:
    _DEFAULT_RETIREMENT_AGE_FALLBACK = 67

from app.services.llm_chat.orchestration_utils_parts.protocol import (
    apply_max_exemption_if_requested,
    build_tool_call_message_content,
    parse_tool_call_from_reply,
    validate_tool_call_protocol_for_execution,
)
from app.services.llm_chat.orchestration_utils_parts.tool_names import (
    get_tool_display_name_hebrew,
    normalize_tool_name,
)

def extract_desired_monthly_income_from_text(user_message: str | None) -> float | None:
    if not user_message:
        return None

    text = str(user_message)
    lowered = text.lower()
    if not lowered.strip():
        return None

    if "תזרים" not in lowered and "cashflow" not in lowered and "הכנסה" not in lowered and "בחודש" not in lowered:
        return None

    cleaned = re.sub(r"[^0-9\s,\.₪\u0590-\u05FF\"']", " ", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    lowered_clean = cleaned.lower()

    def _is_year_marker(num_text: str, start_idx: int) -> bool:
        try:
            n = int(num_text)
        except Exception:
            return False
        if n not in {2000, 2008}:
            return False
        window = lowered_clean[max(0, start_idx - 8) : min(len(lowered_clean), start_idx + 8)]
        return ("אחרי" in window) or ("עד" in window) or ("before" in window) or ("after" in window)

    amount_hints = (
        "₪",
        "שח",
        'ש"ח',
        "שקל",
        "של",
        "בחודש",
        "חודש",
        "הכנסה",
        "צריך",
        "זקוק",
        "יעד",
        "נטו",
        "ברוטו",
    )

    # Support common shorthand: "40 אלף" / "40k".
    # We treat these as explicit user-provided amounts (not estimates).
    for m in re.finditer(r"\b(\d{1,3})\s*(?:אלף|k)\b", lowered_clean, flags=re.IGNORECASE):
        raw_num = str(m.group(1) or "").strip()
        start = int(m.start(1))
        if not raw_num:
            continue
        if _is_year_marker(raw_num, start):
            continue
        try:
            val = float(int(raw_num) * 1000)
        except Exception:
            continue
        if val <= 0:
            continue
        return float(val)

    candidates: list[tuple[int, str]] = []
    for m in re.finditer(r"\b(\d{4,6}(?:,\d{3})*)\b", cleaned):
        raw_num = str(m.group(1) or "")
        start = int(m.start(1))
        if raw_num:
            candidates.append((start, raw_num))

    for start, raw_num in candidates:
        raw_plain = raw_num.replace(",", "").strip()
        if not raw_plain:
            continue
        if _is_year_marker(raw_plain, start):
            continue
        near = lowered_clean[max(0, start - 28) : min(len(lowered_clean), start + 28)]
        if not any(h in near for h in amount_hints):
            continue
        try:
            val = float(raw_plain)
        except Exception:
            continue
        if val <= 0:
            continue
        return float(val)

    return None

def parse_portfolio_wide_prev_employers_severance_conversion_request(
    user_message: str | None,
) -> tuple[list[str], str] | None:
    if not user_message:
        return None

    text = str(user_message)
    lowered = text.lower()

    has_convert_verb = ("המר" in lowered) or ("המרה" in lowered) or ("להמיר" in lowered)
    has_column_clarification = any(
        t in lowered
        for t in (
            "העמודה",
            "השדה",
            "השם המדויק",
            "זה נתון",
            "קיים",
            "קיימת",
            "קיימים",
            "בוודאי",
        )
    )
    if (not has_convert_verb) and (not has_column_clarification):
        return None

    # Detect severance intent for previous employers.
    if ("פיצוי" not in lowered) and ("פיצויים" not in lowered):
        return None
    if ("מעסיק" not in lowered) and ("קודמ" not in lowered):
        return None
    if ("קודמ" not in lowered) and ("previous" not in lowered) and ("prev" not in lowered):
        return None

    # If user explicitly refers to rights sequence, do not auto-run conversion.
    # This component is blocked by business rules and requires external handling.
    if "זכויות" in lowered:
        return ["פיצויים_ממעסיקים_קודמים_רצף_זכויות"], "blocked"

    # Accept common UI/display variants:
    # "פיצויים מעסיקים קודמים (קצבה)" / "... (רצף קצבה)" / "ממעסיקים קודמים".
    if ("קצבה" in lowered) or ("רצף" in lowered):
        return ["פיצויים_ממעסיקים_קודמים_רצף_קצבה"], "pension"

    # Default for ambiguous "מעסיקים קודמים": treat as 'רצף קצבה' (convertible).
    return ["פיצויים_ממעסיקים_קודמים_רצף_קצבה"], "pension"

def parse_portfolio_wide_after_settlement_severance_conversion_request(
    user_message: str | None,
) -> tuple[list[str], str] | None:
    if not user_message:
        return None

    text = str(user_message)
    lowered = text.lower()

    has_convert_verb = ("המר" in lowered) or ("המרה" in lowered) or ("להמיר" in lowered)
    if not has_convert_verb:
        return None

    if ("פיצוי" not in lowered) and ("פיצויים" not in lowered):
        return None

    if ("התחשב" not in lowered) and ("settlement" not in lowered):
        return None

    return ["פיצויים_לאחר_התחשבנות"], "capital_asset"

def extract_process_termination_choice_overrides(user_message: str) -> dict[str, Any]:
    if not isinstance(user_message, str) or not user_message.strip():
        return {}
    lowered = user_message.lower()

    overrides: dict[str, Any] = {}

    # Explicit one-time severance withdrawal: prefer lump-sum unless the user clearly requested annuity.
    annuity_tokens = (
        "רצף קצבה",
        "כקצבה",
        "להמיר לקצבה",
        "annuity",
    )
    lump_sum_tokens = (
        "מענק חד פעמי",
        "מענק חד-פעמי",
        "חד פעמי",
        "חד-פעמי",
        "משיכה חד פעמית",
        "משיכה חד-פעמית",
        "למשוך את כל הפיצויים",
        "משיכת כל הפיצויים",
        "משוך את כל המענקים",
        "משיכת כל המענקים",
        "למשוך את כל המענקים",
        "משיכה הונית",
        "משיכת הון",
        "משיכת מענק",
        "הוני",
        "הונית",
        "הון",
        "lump sum",
        "one-time",
        "one time",
    )
    has_no_annuity_intent = any(
        t in lowered
        for t in (
            "אין צורך בקצבה",
            "אין צורך בעוד קצבה",
            "לא צריך קצבה",
            "בלי קצבה",
            "ללא קצבה",
            "לא קצבה",
        )
    )
    has_lump_sum_intent = any(t in lowered for t in lump_sum_tokens)
    has_any_grant_term = ("פיצויים" in lowered) or ("מענק" in lowered) or ("מענקים" in lowered)

    if "exempt_choice" not in overrides:
        if any(t in lowered for t in ("עם שימוש בפטור", "שימוש בפטור", "עם פטור")) and any(
            t in lowered for t in ("משיכה", "חד פעמ", "חד-פעמ", "הוני", "הונית", "הון")
        ):
            overrides["exempt_choice"] = "redeem_with_exemption"

    if "taxable_choice" not in overrides:
        if ("חייב" in lowered or "חייב במס" in lowered) and (
            "רצף קצבה" in lowered or re.search(r"\bכ?קצבה\b", lowered)
        ):
            overrides["taxable_choice"] = "annuity"

    if has_any_grant_term and has_lump_sum_intent and (not any(t in lowered for t in annuity_tokens) or has_no_annuity_intent):
        overrides.setdefault("exempt_choice", "redeem_with_exemption")
        overrides.setdefault("taxable_choice", "redeem_no_exemption")

    if (
        ("פיצויים" in lowered)
        and ("כקצבה" in lowered or "קצבה" in lowered or "רצף קצבה" in lowered)
        and ("כל" in lowered or "כולם" in lowered)
    ):
        overrides["exempt_choice"] = "annuity"
        overrides["taxable_choice"] = "annuity"

    clauses = [
        c.strip()
        for c in re.split(r"[\n\r\t\.,;:!\?]+", lowered)
        if isinstance(c, str) and c.strip()
    ]

    exempt_clause = next(
        (
            c
            for c in clauses
            if ("מענק" in c)
            and ("פטור" in c)
        ),
        "",
    )
    taxable_clause = next(
        (
            c
            for c in clauses
            if ("מענק" in c)
            and ("חייב" in c)
        ),
        "",
    )

    if exempt_clause:
        if "exempt_choice" not in overrides:
            if any(t in exempt_clause for t in ("עם שימוש בפטור", "שימוש בפטור", "עם פטור")):
                overrides["exempt_choice"] = "redeem_with_exemption"
            elif any(t in exempt_clause for t in ("בלי שימוש בפטור", "ללא שימוש בפטור", "ללא פטור")):
                overrides["exempt_choice"] = "redeem_no_exemption"
            elif "רצף קצבה" in exempt_clause or re.search(r"\bכ?קצבה\b", exempt_clause):
                overrides["exempt_choice"] = "annuity"

    if taxable_clause:
        if "taxable_choice" not in overrides:
            if "רצף קצבה" in taxable_clause or re.search(r"\bכ?קצבה\b", taxable_clause):
                overrides["taxable_choice"] = "annuity"
            elif any(t in taxable_clause for t in ("משיכה", "חד פעמ", "משיכת הון", "משיכת מענק", "הוני")):
                overrides["taxable_choice"] = "redeem_no_exemption"

    if "exempt_choice" not in overrides and ("פטור" in lowered):
        if any(t in lowered for t in ("משיכה", "חד פעמ", "חד-פעמ", "הוני", "הונית", "הון")) and not (
            "רצף קצבה" in lowered or re.search(r"\bכ?קצבה\b", lowered)
        ):
            overrides["exempt_choice"] = "redeem_with_exemption"
        elif "רצף קצבה" in lowered or re.search(r"\bכ?קצבה\b", lowered):
            overrides["exempt_choice"] = "annuity"

    if "taxable_choice" not in overrides and ("חייב" in lowered or "חייב במס" in lowered):
        if any(t in lowered for t in ("משיכה", "חד פעמ", "חד-פעמ", "הוני", "הונית", "הון")) and not (
            "רצף קצבה" in lowered or re.search(r"\bכ?קצבה\b", lowered)
        ):
            overrides["taxable_choice"] = "redeem_no_exemption"

    return overrides

def extract_process_termination_date_override(user_message: str) -> str | None:
    if not isinstance(user_message, str) or not user_message.strip():
        return None

    text = user_message.strip()

    m_dmy = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", text)
    if m_dmy:
        dd = int(m_dmy.group(1))
        mm = int(m_dmy.group(2))
        yyyy = int(m_dmy.group(3))
        if 1 <= dd <= 31 and 1 <= mm <= 12 and 1900 <= yyyy <= 2100:
            return f"{dd:02d}/{mm:02d}/{yyyy:04d}"

    m_iso = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", text)
    if m_iso:
        yyyy = int(m_iso.group(1))
        mm = int(m_iso.group(2))
        dd = int(m_iso.group(3))
        if 1 <= dd <= 31 and 1 <= mm <= 12 and 1900 <= yyyy <= 2100:
            return f"{yyyy:04d}-{mm:02d}-{dd:02d}"

    return None

def parse_partial_pension_conversion_request(user_message: str | None) -> tuple[str, float] | None:
    if not user_message:
        return None

    text = str(user_message)
    lowered = text.lower()

    if ("המר" not in lowered) and ("המרה" not in lowered) and ("להמיר" not in lowered):
        return None
    if ("קצבה" not in lowered) and ("פנסיה" not in lowered):
        return None
    account_number: str | None = None
    m_acc = re.search(
        r"(?:חשבון\s*מספר|מספר\s*חשבון|מספר)\s*([0-9A-Za-z\-]+)",
        text,
        flags=re.IGNORECASE,
    )
    if m_acc:
        account_number = str(m_acc.group(1) or "").strip()

    if not account_number:
        # Common UX: the user writes the account id at the end without saying "מספר חשבון".
        # Prefer 5+ digits to avoid catching years like 2000.
        candidates = re.findall(r"\b(\d{5,})\b", text)
        if candidates:
            account_number = str(candidates[-1] or "").strip()

    if not account_number:
        # Hyphenated ids such as 033-222-697946-1
        hyphenated = re.findall(r"\b(?:\d{2,3}(?:-\d{2,7}){2,})\b", text)
        if hyphenated:
            account_number = str(hyphenated[-1] or "").strip()

    if not account_number:
        return None

    cleaned = re.sub(r"[^0-9a-zA-Z\u0590-\u05FF\s,\.₪]", " ", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    amount: float | None = None
    m_k = re.search(r"\b(\d{1,3})\s*[kK]\b", cleaned)
    if m_k:
        try:
            amount = float(int(m_k.group(1)) * 1000)
        except Exception:
            amount = None

    if amount is None:
        m_he = re.search(r"\b(\d{1,3})\s*אלף\b", cleaned)
        if m_he:
            try:
                amount = float(int(m_he.group(1)) * 1000)
            except Exception:
                amount = None

    if amount is None:
        # Guardrail: avoid treating "אחרי 2000" / "עד 2000" as a requested amount.
        lowered_clean = cleaned.lower()
        amount_hints = (
            "₪",
            "שח",
            'ש"ח',
            "שקל",
            "אלף",
            "k",
            "סכום",
            "בסך",
            "על סך",
            "בגובה",
            "המר",
            "להמיר",
        )

        def _is_year_marker(num_text: str, start_idx: int) -> bool:
            try:
                n = int(num_text)
            except Exception:
                return False
            if n not in {2000, 2008}:
                return False
            window = lowered_clean[max(0, start_idx - 8) : min(len(lowered_clean), start_idx + 8)]
            return ("אחרי" in window) or ("עד" in window) or ("before" in window) or ("after" in window)

        candidates: list[tuple[int, str]] = []
        for m in re.finditer(r"\b(\d{1,9}(?:,\d{3})*)\b", cleaned):
            raw_num = str(m.group(1) or "")
            if not raw_num:
                continue
            start = int(m.start(1))
            candidates.append((start, raw_num))

        chosen_raw: str | None = None
        for start, raw_num in candidates:
            raw_plain = raw_num.replace(",", "").strip()
            if not raw_plain:
                continue
            if _is_year_marker(raw_plain, start):
                continue
            # Require a local hint that this number is an amount (prevents confusing account ids / year markers).
            near = lowered_clean[max(0, start - 12) : min(len(lowered_clean), start + 12)]
            if any(h in near for h in amount_hints):
                chosen_raw = raw_plain
                break

        if chosen_raw is not None:
            try:
                amount = float(chosen_raw)
            except Exception:
                amount = None

    if amount is None or amount <= 0:
        return None

    return account_number, float(amount)

def parse_targeted_component_conversion_request(
    user_message: str | None,
) -> tuple[str, list[str], str] | None:
    if not user_message:
        return None

    text = str(user_message)
    lowered = text.lower()

    if ("המר" not in lowered) and ("המרה" not in lowered) and ("להמיר" not in lowered):
        return None

    # Targeted component conversion should not require "קצבה".
    # We instead require:
    # - explicit account number in the message
    # - explicit tagmulim intent
    # - a concrete time-bucket marker (after/to/before 2000)
    if ("תגמול" not in lowered) and ("תגמולים" not in lowered):
        return None

    # Avoid treating portfolio-wide intents as targeted.
    if any(t in lowered for t in ("בתיק", "תיק", "במערכת")) and any(
        t in lowered for t in ("כל", "כל היתרות", "כל היתרה")
    ):
        return None

    account_number: str | None = None
    m_acc = re.search(
        r"(?:חשבון\s*מספר|מספר\s*חשבון|מספר)\s*([0-9A-Za-z\-]+)",
        text,
        flags=re.IGNORECASE,
    )
    if m_acc:
        account_number = str(m_acc.group(1) or "").strip()

    if not account_number:
        # Common UX: the user writes the account id at the end without saying "מספר חשבון".
        # Prefer 5+ digits to avoid catching years like 2000.
        candidates = re.findall(r"\b(\d{5,})\b", text)
        if candidates:
            account_number = str(candidates[-1] or "").strip()

    if not account_number:
        # Hyphenated ids such as 033-222-697946-1
        hyphenated = re.findall(r"\b(?:\d{2,3}(?:-\d{2,7}){2,})\b", text)
        if hyphenated:
            account_number = str(hyphenated[-1] or "").strip()

    if not account_number:
        return None

    is_after_2000 = bool(re.search(r"אחרי\s*_?\s*2000", lowered))
    is_to_2000 = bool(re.search(r"(?:עד|לפני|לפי|טרום)\s*_?\s*2000", lowered))

    if is_after_2000 and (not is_to_2000):
        fields = ["תגמולי_עובד_אחרי_2000", "תגמולי_מעביד_אחרי_2000"]
        return account_number, fields, "pension"

    if is_to_2000 and (not is_after_2000):
        fields = ["תגמולי_עובד_עד_2000", "תגמולי_מעביד_עד_2000"]
        return account_number, fields, "capital_asset"

    return None

def parse_portfolio_wide_education_fund_conversion_request(user_message: str | None) -> tuple[list[str], str] | None:
    if not user_message:
        return None

    text = str(user_message)
    lowered = text.lower()

    if ("המר" not in lowered) and ("המרה" not in lowered) and ("להמיר" not in lowered):
        return None

    if ("השתלמות" not in lowered) and ("education" not in lowered) and ("study" not in lowered):
        return None

    return ["קרן_השתלמות"], "capital_asset"

def parse_portfolio_wide_component_conversion_request(user_message: str | None) -> tuple[list[str], str] | None:
    if not user_message:
        return None

    text = str(user_message)
    lowered = text.lower()

    if ("המר" not in lowered) and ("המרה" not in lowered) and ("להמיר" not in lowered):
        return None

    if ("תגמול" not in lowered) and ("תגמולים" not in lowered):
        return None

    # Allow short imperative phrasing without requiring explicit "בתיק" / "כל".
    # Example: "בצע המרה של תגמולים לפני 2000".
    imperative_tokens = (
        "בצע",
        "תבצע",
        "נא",
        "בבקשה",
        "please",
        "execute",
        "apply",
        "run",
    )
    has_imperative = any(t in lowered for t in imperative_tokens) or lowered.strip().startswith("המר")
    has_portfolio_scope = any(t in lowered for t in ("תיק", "בתיק", "portfolio", "במערכת"))
    has_all_scope = any(t in lowered for t in ("כל", "כל היתרות", "כל היתרה"))

    # Historically we required portfolio/all markers to reduce false positives, but this caused
    # real user flows to fall back to full-portfolio conversion. For tagmulim + year-marker requests,
    # treat imperative phrasing as sufficient signal.
    if not (has_imperative or has_portfolio_scope or has_all_scope):
        return None

    is_after_2000 = bool(re.search(r"אחרי\s*_?\s*2000", lowered))
    is_to_2000 = bool(re.search(r"(?:עד|לפני|לפי|טרום)\s*_?\s*2000", lowered))

    if is_after_2000 and (not is_to_2000):
        fields: list[str] = [
            "תגמולי_עובד_אחרי_2000",
            "תגמולי_מעביד_אחרי_2000",
            "תגמולי_עובד_אחרי_2008_לא_משלמת",
            "תגמולי_מעביד_אחרי_2008_לא_משלמת",
        ]
        return fields, "pension"

    if is_to_2000 and (not is_after_2000):
        fields = [
            "תגמולי_עובד_עד_2000",
            "תגמולי_מעביד_עד_2000",
        ]
        return fields, "capital_asset"

    return None
