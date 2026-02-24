import json

from app.services.llm_chat.orchestration_utils_parts.tool_names import (
    get_tool_display_name_hebrew,
)


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
            is_error = isinstance(
                tool_result, str
            ) and tool_result.strip().lower().startswith("error:")

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


def build_tool_result_system_message_for_stream(
    tool_name: str, tool_result: str
) -> str:
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
            is_error = isinstance(
                tool_result, str
            ) and tool_result.strip().lower().startswith("error:")

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
