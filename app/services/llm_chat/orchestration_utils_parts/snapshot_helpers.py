"""Utilities for retirement date and age extraction used by orchestration helpers."""

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




def extract_retirement_ages_from_message(user_message: str) -> list[int]:
    if not user_message:
        return []

    text = user_message.lower()

    ages: list[int] = []

    for m in re.finditer(r"גיל\s*(\d{2})", text):
        try:
            ages.append(int(m.group(1)))
        except Exception:
            continue

    for m in re.finditer(r"(?:מול|לעומת|בין|vs|versus)\s*(\d{2})", text):
        try:
            ages.append(int(m.group(1)))
        except Exception:
            continue

    normalized: list[int] = []
    for a in ages:
        if a < 40 or a > 80:
            continue
        if a not in normalized:
            normalized.append(a)

    return normalized

def build_tool_result_system_message_for_chat(tool_name: str, tool_result: str) -> str:
    tool_display = get_tool_display_name_hebrew(tool_name)
    if tool_name == "GENERATE_FULL_REPORT":
        return (
            f"🔧 **פלט כלי ({tool_display}):**\n"
            f"{tool_result}\n\n"
            "הנחיות למודל: הדוח כולל את המידע והחישובים הרלוונטיים כפי שנוצרו בדוח עצמו. "
            "אל תציע לבצע חישובי מס נוספים או הרצות כלים נוספות, אלא אם המשתמש ביקש זאת במפורש. "
            "התמקד בסיכום קצר וברור ובהפניה לקישור/נתיב הדוח."
        )

    if tool_name == "CALCULATE_FIXATION_OF_RIGHTS":
        safe_tool_result = tool_result
        try:
            parsed_fix = json.loads(tool_result)
            if isinstance(parsed_fix, dict):
                parsed_fix.pop("remaining_monthly_exemption", None)
                parsed_fix.pop("remaining_exempt_capital", None)
                safe_tool_result = json.dumps(parsed_fix, ensure_ascii=False)
        except Exception:
            safe_tool_result = tool_result
        return (
            f"🔧 **פלט כלי ({tool_display}):**\n"
            f"{safe_tool_result}\n\n"
            "הנחיות למודל: בעת סיכום קיבוע זכויות, אל תציג ואל תסיק מסקנות מהשדות remaining_monthly_exemption ו-remaining_exempt_capital. "
            "הם אינם חלק מהתצוגה הנכונה למשתמש. התבסס רק על שנת קיבוע, קצבה פטורה חודשית, אחוז קצבה פטורה, והון פטור ראשוני (אם קיים)."
        )

    if tool_name == "TRANSFORM_FUNDS_TO_ASSETS":
        is_error = False
        parsed_success: dict | None = None
        try:
            parsed = json.loads(tool_result)
            if isinstance(parsed, dict) and parsed.get("success") is False:
                is_error = True
            if isinstance(parsed, dict) and parsed.get("success") is True:
                parsed_success = parsed
        except Exception:
            is_error = isinstance(tool_result, str) and tool_result.strip().lower().startswith("error:")

        if is_error:
            return (
                f"🔧 **פלט כלי ({tool_display}):**\n"
                f"{tool_result}\n\n"
                "הנחיות למודל: ההמרה נכשלה ולכן לא בוצעה שום המרה (converted_count=0). "
                "אסור לטעון שבוצעה המרה חלקית של יתרות לא חסומות. "
                "אם נדרש ניתוח פרישה/השוואה, ציין במפורש שהניתוח מבוסס על הנתונים הקיימים לפני ההמרה בלבד."
            )

        if parsed_success is not None:
            return (
                f"🔧 **פלט כלי ({tool_display}):**\n"
                f"{tool_result}\n\n"
                "הנחיות למודל: זהו כלי ביצוע. מותר לך לטעון שבוצעה המרה אך ורק לפי הנתונים שמוחזרים כאן. "
                "בעת סיכום הפעולה, חובה להתבסס רק על converted_items ו-skipped_items (ועל employer_current_severance_not_converted אם קיים). "
                "אסור להוסיף/להמציא המרות, איפוסים, מחיקות, או שינויי יתרות שלא מופיעים בפלט ה-JSON של הכלי."
            )

    return (
        f"🔧 **פלט כלי ({tool_display}):**\n"
        f"{tool_result}\n\n"
        "הנחיות למודל: השתמש בנתוני הכלי האלה (ברוטו, נטו, מס, ופרטי פטור אם קיימים) כדי לבנות תשובה אחת סופית וברורה למשתמש על הקצבה נטו אחרי מס. "
        "אל תחזור על ה-JSON הגולמי ואל תיתן תשובה נפרדת רק עבור הכלי עצמו."
    )

def build_tool_result_system_message_for_stream(tool_name: str, tool_result: str) -> str:
    tool_display = get_tool_display_name_hebrew(tool_name)
    if tool_name == "GENERATE_FULL_REPORT":
        return (
            f"פלט כלי ({tool_display}): {tool_result}\n\n"
            "הנחיות למודל: הדוח כולל את המידע והחישובים הרלוונטיים כפי שנוצרו בדוח עצמו. "
            "אל תציע לבצע חישובי מס נוספים או הרצות כלים נוספות, אלא אם המשתמש ביקש זאת במפורש. "
            "התמקד בסיכום קצר ובהפניה לקישור/נתיב הדוח."
        )

    if tool_name == "CALCULATE_FIXATION_OF_RIGHTS":
        safe_tool_result = tool_result
        try:
            parsed_fix = json.loads(tool_result)
            if isinstance(parsed_fix, dict):
                parsed_fix.pop("remaining_monthly_exemption", None)
                parsed_fix.pop("remaining_exempt_capital", None)
                safe_tool_result = json.dumps(parsed_fix, ensure_ascii=False)
        except Exception:
            safe_tool_result = tool_result
        return (
            f"פלט כלי ({tool_display}): {safe_tool_result}\n\n"
            "הנחיות למודל: בעת סיכום קיבוע זכויות, אל תציג ואל תסיק מסקנות מהשדות remaining_monthly_exemption ו-remaining_exempt_capital. "
            "הם אינם חלק מהתצוגה הנכונה למשתמש. התבסס רק על שנת קיבוע, קצבה פטורה חודשית, אחוז קצבה פטורה, והון פטור ראשוני (אם קיים)."
        )

    if tool_name == "TRANSFORM_FUNDS_TO_ASSETS":
        is_error = False
        parsed_success: dict | None = None
        try:
            parsed = json.loads(tool_result)
            if isinstance(parsed, dict) and parsed.get("success") is False:
                is_error = True
            if isinstance(parsed, dict) and parsed.get("success") is True:
                parsed_success = parsed
        except Exception:
            is_error = isinstance(tool_result, str) and tool_result.strip().lower().startswith("error:")

        if is_error:
            return (
                f"פלט כלי ({tool_display}): {tool_result}\n\n"
                "הנחיות למודל: ההמרה נכשלה ולכן לא בוצעה שום המרה (converted_count=0). "
                "אסור לטעון שבוצעה המרה חלקית של יתרות לא חסומות. "
                "אם נדרש ניתוח פרישה/השוואה, ציין במפורש שהניתוח מבוסס על הנתונים הקיימים לפני ההמרה בלבד."
            )

        if parsed_success is not None:
            return (
                f"פלט כלי ({tool_display}): {tool_result}\n\n"
                "הנחיות למודל: סכם את הפעולה רק לפי converted_items ו-skipped_items (ועל employer_current_severance_not_converted אם קיים). "
                "אסור לטעון על המרות/איפוסים/מחיקות מאחורי הקלעים שלא מופיעים בפלט הכלי."
            )

    return (
        f"פלט כלי ({tool_display}): {tool_result}\n\n"
        "הנחיות למודל: שלב את נתוני הכלי (ברוטו, נטו, מס ופרטי פטור) בתוך תשובה אחת סופית וברורה ללקוח על הקצבה נטו, "
        "ואל תחזור על ה-JSON עצמו כלשונו."
    )

def build_tax_result_system_message_for_chat(tax_result: str) -> str:
    tool_display = get_tool_display_name_hebrew("GET_TAX_PROJECTION")
    return (
        f"🔧 **פלט כלי ({tool_display} - שרשור אוטומטי):**\n{tax_result}\n\n"
        "הנחיות למודל: שלב את תוצאת GET_TAX_PROJECTION (שיעור מס אפקטיבי, מס חודשי וכו') יחד עם נתוני RUN_RETIREMENT_CASHFLOW_ANALYSIS שכבר קיבלת. "
        "עליך להסביר ללקוח קצבה ברוטו, מס, וקצבה נטו, ולהדגיש את השפעת הפטור המקסימלי (אם הופעל) על המס והנטו. אל תחזיר פלט כפול או לא מאוחד."
    )

def build_tax_result_system_message_for_stream(tax_result: str) -> str:
    tool_display = get_tool_display_name_hebrew("GET_TAX_PROJECTION")
    return (
        f"פלט כלי ({tool_display}): {tax_result}\n\n"
        "הנחיות למודל: שלב את נתוני המס (שיעור מס אפקטיבי, מס חודשי וכו') יחד עם תוצאת ניתוח הפרישה הקודמת, "
        "ונתֵח עבור הלקוח את הקצבה ברוטו, המס והקצבה נטו, תוך הדגשת תרומת הפטור המקסימלי אם הופעל."
    )

def compute_retirement_date_from_birth_date(birth_date: date, retirement_age: int) -> date:
    try:
        return birth_date + relativedelta(years=int(retirement_age))
    except ValueError:
        return birth_date.replace(
            year=birth_date.year + int(retirement_age),
            day=min(birth_date.day, 28),
        )

def normalize_retirement_date_if_jan1_placeholder(
    retirement_date: str,
    birth_date: date,
    user_message: str,
) -> str:
    if not retirement_date or not birth_date:
        return retirement_date

    try:
        parsed = datetime.strptime(retirement_date, "%Y-%m-%d").date()
    except Exception:
        return retirement_date

    if parsed.month != 1 or parsed.day != 1:
        return retirement_date

    requested_ages = extract_retirement_ages_from_message(user_message)
    if not requested_ages:
        return retirement_date

    implied_age = relativedelta(parsed, birth_date).years

    if implied_age in requested_ages:
        return compute_retirement_date_from_birth_date(birth_date, implied_age).isoformat()

    if len(requested_ages) == 1:
        return compute_retirement_date_from_birth_date(birth_date, requested_ages[0]).isoformat()

    return retirement_date

def compute_default_retirement_date_for_tool_call(*, birth_date: date | None, gender: str | None, user_message: str) -> str:
    if birth_date is None:
        return date.today().isoformat()

    requested_ages = extract_retirement_ages_from_message(user_message)
    if len(requested_ages) == 1:
        return compute_retirement_date_from_birth_date(birth_date, requested_ages[0]).isoformat()

    try:
        legal_retirement_date = get_retirement_date(birth_date, gender or "")
    except Exception:
        try:
            from app.services.retirement_age_service import DEFAULT_MALE_RETIREMENT_AGE

            fallback_age = int(DEFAULT_MALE_RETIREMENT_AGE)
        except Exception:
            fallback_age = int(_DEFAULT_RETIREMENT_AGE_FALLBACK)
        try:
            from app.services.retirement_age_service import get_retirement_age_simple

            fallback_age = int(get_retirement_age_simple(birth_date, gender or ""))
        except Exception:
            try:
                from app.services.retirement_age_service import DEFAULT_MALE_RETIREMENT_AGE

                fallback_age = int(DEFAULT_MALE_RETIREMENT_AGE)
            except Exception:
                fallback_age = int(_DEFAULT_RETIREMENT_AGE_FALLBACK)
        legal_retirement_date = compute_retirement_date_from_birth_date(birth_date, fallback_age)

    today = date.today()
    if legal_retirement_date < today:
        return today.isoformat()
    return legal_retirement_date.isoformat()

