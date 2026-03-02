"""Guards and validations (is_*/infer_*/_is_* helpers) for chat orchestration."""

# NOTE: This module will be filled by move-only extraction from orchestration_utils.py.
# Keep bodies 1:1 when moving functions.

import json
import re
from datetime import date, datetime
from typing import Any

from dateutil.relativedelta import relativedelta

from app.services.retirement_age_service import get_retirement_date

try:
    from app.services.retirement_age_service import (
        DEFAULT_MALE_RETIREMENT_AGE as _DEFAULT_RETIREMENT_AGE_FALLBACK,
    )
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


def is_net_pension_request(user_message: str) -> bool:
    net_keywords = ["נטו", "ביד", "אחרי מס", "נקי", "net"]
    message_lower = (user_message or "").lower()
    return any(keyword in message_lower for keyword in net_keywords)


def _is_target_pension_plan_request_text(user_message: str) -> bool:
    lowered = (user_message or "").lower().replace(",", "")
    if not lowered.strip():
        return False

    if ("תזרים" in lowered) or ("cashflow" in lowered):
        return False
    planning_keywords = [
        "יעד קצבה",
        "מתווה",
        "תכנית",
        "תוכנית",
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


def is_data_awareness_request(user_message: str | None) -> bool:
    if not user_message:
        return False
    lowered = str(user_message).lower()
    if not lowered.strip():
        return False
    triggers = (
        "מודע",
        "אתה יודע",
        "יודע",
        "כל נתוני",
        "כל הנתונים",
        "נתוני התיק",
        "מקורות הכנסה",
        "מקורות ההכנסה",
        "כל מקורות",
    )
    return any(t in lowered for t in triggers) and ("?" in lowered or "האם" in lowered)


def is_list_all_financial_entities_request(user_message: str | None) -> bool:
    if not user_message:
        return False
    lowered = str(user_message).strip().lower()
    if not lowered:
        return False

    action_triggers = ("תציג", "הצג", "פרט", "פירוט", "רשימה", "show", "list")
    entity_triggers = (
        "הכנסות",
        "הכנסה",
        "קצבאות",
        "קצבה",
        "נכסי הון",
        "נכס הון",
        "נכסים",
        "capital",
        "income",
        "pension",
    )

    if not any(t in lowered for t in action_triggers):
        return False
    if not any(t in lowered for t in entity_triggers):
        return False
    if "בפועל" in lowered and "במערכת" in lowered:
        return False
    return True


def infer_desired_income_is_net_explicit(user_message: str | None) -> bool | None:
    if not user_message:
        return None
    lowered = str(user_message).strip().lower()
    if not lowered:
        return None

    net_triggers = (
        "נטו",
        "אחרי מס",
        "אחרי המס",
        "לאחר מס",
        "לאחר המס",
        "net",
    )
    gross_triggers = (
        "ברוטו",
        "לפני מס",
        "לפני המס",
        "gross",
    )

    if any(t in lowered for t in net_triggers):
        return True
    if any(t in lowered for t in gross_triggers):
        return False
    return None


def is_cashflow_missing_income_followup(user_message: str | None) -> bool:
    if not user_message:
        return False
    lowered = str(user_message).strip().lower()
    if not lowered:
        return False
    if any(t in lowered for t in ("לא הכנסת", "לא התחשבת", "התעלמת")) and any(
        t in lowered
        for t in (
            "הכנסה",
            "הכנסות",
            "הכנסה נוספת",
            "additionalincome",
            "קצבה",
            "קצבאות",
        )
    ):
        return True
    return False


def is_retirement_cashflow_request(user_message: str) -> bool:
    if not user_message:
        return False

    if is_process_termination_request(user_message):
        return False

    lowered = user_message.lower()
    if ("תזרים" in lowered) or ("cashflow" in lowered):
        return True

    if _is_target_pension_plan_request_text(user_message):
        return False

    if is_transform_request(user_message):
        return False

    if is_document_request(user_message):
        return False

    if is_tax_documents_request(user_message):
        return False

    compute_tokens = (
        "תחשב",
        "תחישב",
        "חשב",
        "חישוב",
        "ניתוח",
        "תריץ",
        "הרץ",
    )
    domain_tokens = (
        "פרישה",
        "תאריך פרישה",
        "גיל פרישה",
        "קצבה",
        "פנסיה",
        "נטו",
        "ברוטו",
        "מס",
        "יעד",
        "תרחיש",
    )

    # Only treat as a cashflow request when the user explicitly asked to compute/run an analysis.
    return any(t in lowered for t in compute_tokens) and any(
        t in lowered for t in domain_tokens
    )


def is_process_termination_request(user_message: str) -> bool:
    if not user_message:
        return False

    lowered = user_message.lower()

    # Do not treat explicit portfolio component conversion requests as work-termination execution.
    # Example: "בצע המרה של פיצויים מעסיקים קודמים (קצבה)" / "בצע המרה של פיצויים לאחר התחשבנות".
    explicit_termination_keywords = (
        "עזיבת עבודה",
        "עזיבת העבודה",
        "סיום עבודה",
        "סיום העבודה",
        "process_termination",
        "process termination",
        "termination",
    )
    has_explicit_termination_intent = any(
        k in lowered for k in explicit_termination_keywords
    )
    if not has_explicit_termination_intent:
        has_convert_verb = (
            ("המר" in lowered)
            or ("המרה" in lowered)
            or ("להמיר" in lowered)
            or ("convert" in lowered)
        )
        component_intent_tokens = (
            "מעסיקים קודמים",
            "ממעסיקים קודמים",
            "מעסיק קודמ",
            "קודמ",
            "לאחר התחשבנות",
            "לאחר התחשב",
            "התחשבנות",
            "התחשב",
            "רצף קצבה",
            "רצף",
        )
        if has_convert_verb and any(t in lowered for t in component_intent_tokens):
            return False

    # If the user asked for a conceptual explanation only (no execution), we still
    # want to route to the termination flow so it can return a termination-specific
    # principle-only response (execution is blocked elsewhere).
    try:
        from app.guards.tool_intent_guard import is_conceptual_no_execute_request

        if has_explicit_termination_intent and is_conceptual_no_execute_request(
            user_message
        ):
            return True
    except Exception:
        pass

    action_tokens = [
        "בצע",
        "תבצע",
        "הפעל",
        "להפעיל",
        "עדכן",
        "לעדכן",
        "במערכת",
        "מאשר",
        "מאשרת",
        "אני מאשר",
        "אני מאשרת",
        "מאושר",
        "אישור",
        "מסכים",
        "מסכימה",
        "רוצה",
        "רוצה ש",
        "מעוניין",
        "מעוניינת",
        "מבקש",
        "מבקשת",
        "please",
        "execute",
        "apply",
        "run",
        "process_termination",
    ]
    domain_tokens = [
        "עזיבת עבודה",
        "עזיבת העבודה",
        "סיום עבודה",
        "סיום העבודה",
        "termination",
        "פיצויים",
        "פיצוי",
        "מענק",
        "מענק פטור",
        "severance",
        "מעסיק נוכחי",
    ]

    return any(a in lowered for a in action_tokens) and any(
        d in lowered for d in domain_tokens
    )


def is_no_termination_request(user_message: str) -> bool:
    if not user_message:
        return False
    lowered = (user_message or "").lower()
    negative_tokens = (
        "אל תשתמש",
        "לא להשתמש",
        "אל תבצע",
        "לא לבצע",
        "ביקשתי שלא",
        "בלי",
    )
    domain_tokens = (
        "process_termination",
        "process termination",
        "termination",
        "סיום עבודה",
        "עזיבת עבודה",
        "פיצויים",
    )
    return any(t in lowered for t in negative_tokens) and any(
        t in lowered for t in domain_tokens
    )


def is_termination_change_request(user_message: str) -> bool:
    if not user_message:
        return False

    lowered = user_message.lower()

    change_tokens = [
        "שנה",
        "לשנות",
        "עדכן",
        "לעדכן",
        "תעדכן",
        "החלף",
        "להחליף",
        "במקום",
        "לבטל",
        "בטל",
        "תיקון",
        "update",
        "change",
        "modify",
    ]
    domain_tokens = [
        "process_termination",
        "עזיבת עבודה",
        "סיום עבודה",
        "termination",
        "פיצויים",
        "severance",
        "רצף",
        "רצף קצבה",
        "קצבה",
        "משיכה",
    ]

    return any(t in lowered for t in change_tokens) and any(
        d in lowered for d in domain_tokens
    )


def is_retirement_comparison_request(user_message: str) -> bool:
    if not user_message:
        return False

    lowered = user_message.lower()

    comparison_triggers = [
        "השווא",
        "לעומת",
        "מול",
        "בין",
        "vs",
        "versus",
    ]

    has_comparison = any(t in lowered for t in comparison_triggers)
    if not has_comparison:
        return False

    lowered = user_message.lower()
    retirement_tokens = (
        "פרישה",
        "גיל פרישה",
        "תאריך פרישה",
        "קצבה",
        "פנסיה",
        "תזרים",
        "cashflow",
        "נטו",
        "ברוטו",
    )
    return any(t in lowered for t in retirement_tokens)


def is_max_exemption_request(user_message: str) -> bool:
    if not user_message:
        return False
    keywords = [
        "פטור מקסימלי",
        "מיצוי הפטור המקסימלי",
        "מיצוי פטור מלא",
        "פטור מלא על הקצבה",
        "פטור מלא לקצבה",
        "קיבוע זכויות",
        "max exemption",
        "maximum exemption",
    ]
    lowered = user_message.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def is_document_request(user_message: str) -> bool:
    if not user_message:
        return False

    lowered = user_message.lower()

    doc_keywords = [
        "דוח",
        'דו"ח',
        "מסמך",
        "pdf",
        "להורדה",
        "הורדה",
        "download",
        "קישור",
        "link",
    ]

    intent_keywords = [
        "הפק",
        "להפיק",
        "תפיק",
        "תייצר",
        "לייצר",
        "תכין",
        "להכין",
        "תן לי",
        "שלח",
        "generate",
        "produce",
    ]

    has_doc_keyword = any(k in lowered for k in doc_keywords)
    has_intent_keyword = any(k in lowered for k in intent_keywords)

    if has_doc_keyword and has_intent_keyword:
        return True

    if not has_doc_keyword:
        return False

    direct_doc_intents = [
        "קיבוע",
        "זכויות",
        "טופס",
        "161",
        "אישור",
        "פריסה",
        "פריסת",
        "פטור",
    ]
    return any(k in lowered for k in direct_doc_intents)


def is_tax_documents_request(user_message: str) -> bool:
    if not user_message:
        return False

    lowered = user_message.lower()

    doc_signal_keywords = [
        "מסמך",
        "מסמכי",
        "pdf",
        "טופס",
        "אישור",
        "להורדה",
        "הורדה",
        "קישור",
        "download",
        "link",
    ]
    if not any(k in lowered for k in doc_signal_keywords):
        return False

    tax_doc_keywords = [
        "קיבוע",
        "זכויות",
        "161",
        "טופס 161",
        "מסמכי מס",
        "פקיד שומה",
        "רשות המיסים",
        "אישור פטור",
        "פטור פיצויים",
        "פריסת מס",
    ]
    return any(k in lowered for k in tax_doc_keywords)


def is_full_report_request(user_message: str) -> bool:
    if not user_message:
        return False

    if not is_document_request(user_message):
        return False

    lowered = user_message.lower()
    report_keywords = [
        "דוח",
        'דו"ח',
        "report",
        "html",
        "עמוד דוחות",
    ]
    return any(k in lowered for k in report_keywords)


def is_max_capital_request(user_message: str) -> bool:
    if not user_message:
        return False

    lowered = (user_message or "").lower()
    if not lowered.strip():
        return False

    if "מקסימום הון" in lowered:
        return True
    if "מקסימום הוני" in lowered:
        return True
    if "משיכה הונית" in lowered:
        return True
    if "בצורה הונית" in lowered:
        return True
    if "הונית" in lowered or "הוני" in lowered:
        if any(
            k in lowered
            for k in (
                "משוך",
                "משיכה",
                "למשוך",
                "משוך את כל",
                "כל התיק",
                "כל הסכומים",
                "100%",
            )
        ):
            return True
    return False


def infer_tax_document_type(user_message: str) -> str:
    lowered = (user_message or "").lower()

    if "טופס 161" in lowered or "161" in lowered:
        return "form_161"
    if "פריסת" in lowered or "פריסה" in lowered:
        return "tax_spread"
    if "פטור" in lowered and "פיצוי" in lowered:
        return "ptor_pitzuim"

    return "kibua_zechuyot"


def is_pension_commutation_request(user_message: str) -> bool:
    if not user_message:
        return False

    lowered = user_message.lower()
    # Treat any explicit mention of pension commutation (היוון) as commutation intent.
    # This is intentionally permissive to avoid accidental routing to TRANSFORM_FUNDS_TO_ASSETS.
    if (
        "היוון" in lowered
        or "להוון" in lowered
        or "הוון" in lowered
        or "commutation" in lowered
    ):
        return True
    return False


def is_transform_request(user_message: str) -> bool:
    if not user_message:
        return False

    lowered = user_message.lower()

    # Safety: do not treat tax / "how much tax" questions as an implicit request to mutate state.
    # These questions should be answered analytically (e.g., via GET_TAX_PROJECTION) without transforming the portfolio.
    tax_intent_markers = ["כמה מס", "מס אשלם", "מס על", "tax"]
    if any(m in lowered for m in tax_intent_markers):
        return False

    # Only consider transformation when there's an explicit conversion/execution verb.
    # Withdrawal language alone (e.g. "משוך קצבה") is ambiguous and must not trigger a DB mutation.
    explicit_convert_markers = [
        "transform_funds_to_assets",
        "המר",
        "להמיר",
        "המרה",
        "convert",
        "conversion",
        "transform funds",
    ]
    if not any(m in lowered for m in explicit_convert_markers):
        return False

    # Pension commutation (היוון קצבה) is NOT a portfolio transformation.
    # Avoid routing commutation requests to TRANSFORM_FUNDS_TO_ASSETS.
    commutation_keywords = [
        "היוון",
        "היוון קצבה",
        "commutation",
    ]
    if any(k in lowered for k in commutation_keywords):
        return False

    analysis_intent_keywords = [
        "בצע ניתוח",
        "תבצע ניתוח",
        "ניתוח",
        "נתח",
        "analyse",
        "analyze",
        "analysis",
        "אפשרויות משיכה",
        "אפשרויות המשיכה",
        "אופציות משיכה",
        "withdrawal options",
        "withdraw options",
    ]
    if any(k in lowered for k in analysis_intent_keywords):
        return False

    # Only block explicit work-termination flows. General severance conversion requests (e.g.
    # "המר את הפיצויים ממעסיקים קודמים") should still route to TRANSFORM_FUNDS_TO_ASSETS.
    termination_intent_keywords = [
        "עזיבת עבודה",
        "עזיבת העבודה",
        "סיום עבודה",
        "סיום העבודה",
        "process_termination",
        "termination",
    ]
    if any(k in lowered for k in termination_intent_keywords):
        return False

    triggers = [
        "transform_funds_to_assets",
        "המר",
        "להמיר",
        "המרה",
        "פיצויים ממעסיקים קודמים",
        "פיצויים מעסיקים קודמים",
        "convert",
        "conversion",
        "transform funds",
    ]

    return any(t in lowered for t in triggers)


def is_portfolio_breakdown_request(user_message: str) -> bool:
    if not user_message:
        return False

    lowered = user_message.lower()

    has_analysis_intent = False

    planning_intent_keywords = [
        "תכנית משיכה",
        "תוכנית משיכה",
        "מתווה משיכה",
        "יעד קצבה",
        "יעד",
        "צור תכנית",
        "צור תוכנית",
        "בנה תכנית",
        "בנה תוכנית",
        "תכנן",
        "תכנון",
        "build_target_pension_plan",
        "plan",
    ]
    has_planning_intent = any(k in lowered for k in planning_intent_keywords)
    mentions_pension_goal = "קצבה" in lowered or "פנסיה" in lowered
    if has_planning_intent and mentions_pension_goal:
        return False

    # Common goal phrasing: "אני צריך/זקוק לקצבה" + a numeric target (e.g., 25K / 25000)
    has_need_phrase = any(
        k in lowered
        for k in [
            "צריך קצבה",
            "זקוק לקצבה",
            "זקוקה לקצבה",
            "אני צריך קצבה",
            "אני זקוק לקצבה",
        ]
    )
    has_numeric_target = bool(re.search(r"\b\d{2,3}\s*k\b", lowered)) or bool(
        re.search(r"\b\d{4,6}\b", lowered)
    )
    if has_need_phrase and has_numeric_target:
        return False

    portfolio_keywords = [
        "תיק פנסיוני",
        "תיק הפנסיוני",
        "התיק",
        "נכסי פנסיה",
        "נכסים פנסיוניים",
        "פירוט",
        "טבלת",
        "מוצרים",
        "מסלקה",
        "portfolio",
        "breakdown",
    ]

    if not any(k.lower() in lowered for k in portfolio_keywords):
        return False

    triggers = [
        "סכם",
        "סיכום",
        "תסכם",
        "סכמ",
        "פירוט",
        "הצג",
        "תציג",
        "טבלה",
        "רשימה",
        "חלוקה",
        "breakdown",
        "summary",
    ]
    return has_analysis_intent or any(t in lowered for t in triggers)


def is_portfolio_analysis_request(user_message: str) -> bool:
    if not user_message:
        return False

    lowered = user_message.lower()

    analysis_intent_keywords = [
        "בצע ניתוח",
        "תבצע ניתוח",
        "ניתוח",
        "נתח",
        "analyse",
        "analyze",
        "analysis",
        "אפשרויות משיכה",
        "אפשרויות המשיכה",
        "אופציות משיכה",
        "withdrawal options",
        "withdraw options",
    ]
    if not any(k in lowered for k in analysis_intent_keywords):
        return False

    portfolio_keywords = [
        "תיק",
        "תיק פנסיוני",
        "תיק הפנסיוני",
        "התיק",
        "נכסי פנסיה",
        "נכסים פנסיוניים",
        "מוצרים",
        "מסלקה",
        "portfolio",
    ]
    return any(k in lowered for k in portfolio_keywords)


def is_no_tools_request(user_message: str) -> bool:
    if not user_message:
        return False

    lowered = user_message.lower()

    triggers = [
        "אין להריץ שום כלי",
        "אין להריץ כלים",
        "לא להריץ שום כלי",
        "לא להפעיל כלים",
        "אל תפעיל כלים",
        "אל תפעיל כלי",
        "אל תפעיל שום כלי",
        "בלי כלים",
        "ללא כלים",
        "בלי להשתמש בכלי",
        "בלי להשתמש בכלים",
        "בלי שימוש בכלים",
        "רק במילים",
        "ענה רק במילים",
        "במילים בלבד",
        "words only",
        "text only",
        "no tool",
        "no tools",
        "without tools",
        "do not run any tool",
        "dont run any tool",
    ]

    return any(t in lowered for t in triggers)


def is_qa_request(user_message: str) -> bool:
    if not user_message:
        return False

    lowered = user_message.lower()

    triggers = [
        "qa",
        "בדיקת מערכת",
        "בדיקת מערכת מקיפה",
        "בדיקת כפילויות",
        "get_pension_products",
        "transform_funds_to_assets",
        "generate_full_report",
        "דרישות יציאה",
        "pass רק",
        "pass only",
    ]

    return any(t.lower() in lowered for t in triggers)
