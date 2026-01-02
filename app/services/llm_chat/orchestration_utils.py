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


def get_tool_display_name_hebrew(tool_name: str | None) -> str:
    if not isinstance(tool_name, str) or not tool_name.strip():
        return "כלי"

    mapping = {
        "BUILD_TARGET_PENSION_PLAN": "בניית תכנית קצבה",
        "GET_TAX_PROJECTION": "הערכת מס",
        "GET_PENSION_PRODUCTS": "שליפת מוצרים בתיק",
        "CHECK_DATA_COMPLETENESS": "בדיקת שלמות נתונים",
        "CALCULATE_TAX_EXEMPT_PENSION": "חישוב קצבה פטורה",
        "RUN_RETIREMENT_CASHFLOW_ANALYSIS": "ניתוח פרישה",
        "RUN_RETIREMENT_SCENARIOS": "הרצת תרחישי פרישה",
        "SELECT_TARGET_PENSION_SCENARIO": "בחירת תרחיש ליעד",
        "FIND_OPTIMAL_SCENARIO": "מציאת תרחיש אופטימלי",
        "EXECUTE_RETIREMENT_SCENARIO": "החלת תרחיש",
        "CALCULATE_PENSION_COMMUTATION": "חישוב היוון קצבה",
        "CALCULATE_FIXATION_OF_RIGHTS": "חישוב קיבוע זכויות",
        "CALCULATE_CAPITAL_WITHDRAWAL_TAX": "חישוב מס על משיכת הון",
        "CALCULATE_TAX_SPREAD_BENEFIT": "חישוב הטבת מס בפריסה",
        "PROCESS_TERMINATION": "עזיבת עבודה (מעסיק נוכחי)",
        "PROJECT_TOTAL_ANNUITY": "חישוב קצבה כוללת",
        "GET_ACCOUNT_DETAILS": "שליפת פרטי חשבון",
        "SUBMIT_TAX_COMMUTATION": "ביצוע קיבוע/היוון/פריסה",
        "EXECUTE_PENSION_COMMUTATION": "ביצוע היוון קצבה",
        "GENERATE_FULL_REPORT": "הפקת דוח",
        "GENERATE_TAX_DEDUCTION_DOCUMENTS": "הפקת מסמכי מס",
        "TRANSFORM_FUNDS_TO_ASSETS": "המרת תיק לנכסים",
        "CREATE_INDIVIDUAL_ASSET": "יצירת נכס ידני",
        "CREATE_TAX_EXEMPT_GRANT": "יצירת מענק פטור",
        "SET_CURRENT_EMPLOYER_DETAILS": "עדכון פרטי מעסיק נוכחי",
        "EXECUTE_WORK_TERMINATION": "ביצוע עזיבת עבודה",
    }
    return mapping.get(tool_name, tool_name)


def normalize_tool_name(tool_name: str | None) -> str | None:
    if tool_name is None:
        return None

    if not isinstance(tool_name, str):
        return tool_name

    normalized = tool_name.strip()
    if not normalized:
        return tool_name

    # Keep canonical tool constants as-is
    upper = normalized.upper()
    known_constants = {
        "BUILD_TARGET_PENSION_PLAN",
        "GET_TAX_PROJECTION",
        "GET_PENSION_PRODUCTS",
        "CHECK_DATA_COMPLETENESS",
        "CALCULATE_TAX_EXEMPT_PENSION",
        "RUN_RETIREMENT_CASHFLOW_ANALYSIS",
        "RUN_RETIREMENT_SCENARIOS",
        "SELECT_TARGET_PENSION_SCENARIO",
        "FIND_OPTIMAL_SCENARIO",
        "EXECUTE_RETIREMENT_SCENARIO",
        "CALCULATE_PENSION_COMMUTATION",
        "CALCULATE_CAPITAL_WITHDRAWAL_TAX",
        "CALCULATE_TAX_SPREAD_BENEFIT",
        "PROCESS_TERMINATION",
        "PROJECT_TOTAL_ANNUITY",
        "GET_ACCOUNT_DETAILS",
        "SUBMIT_TAX_COMMUTATION",
        "EXECUTE_PENSION_COMMUTATION",
        "GENERATE_FULL_REPORT",
        "GENERATE_TAX_DEDUCTION_DOCUMENTS",
        "TRANSFORM_FUNDS_TO_ASSETS",
        "CREATE_INDIVIDUAL_ASSET",
        "CREATE_TAX_EXEMPT_GRANT",
        "CREATE_ADDITIONAL_INCOME",
        "SET_CURRENT_EMPLOYER_DETAILS",
        "EXECUTE_WORK_TERMINATION",
        "CALCULATE_FIXATION_OF_RIGHTS",
    }
    if upper in known_constants:
        return upper

    lowered = normalized.lower()
    hebrew_map = {
        "סיום עבודה": "PROCESS_TERMINATION",
        "עזיבת עבודה": "PROCESS_TERMINATION",
        "עזיבת עבודה (מעסיק נוכחי)": "PROCESS_TERMINATION",
        "סיום עבודה (מעסיק נוכחי)": "PROCESS_TERMINATION",
        "סיום עבודה למעסיק הנוכחי": "PROCESS_TERMINATION",
        "ביצוע עזיבת עבודה": "PROCESS_TERMINATION",
        "בצע עזיבת עבודה": "PROCESS_TERMINATION",
        "המרת תיק לנכסים": "TRANSFORM_FUNDS_TO_ASSETS",
        "ניתוח פרישה": "RUN_RETIREMENT_CASHFLOW_ANALYSIS",
        "הערכת מס": "GET_TAX_PROJECTION",
        "בניית תכנית קצבה": "BUILD_TARGET_PENSION_PLAN",
        "קיבוע": "CALCULATE_FIXATION_OF_RIGHTS",
        "קיבוע זכויות": "CALCULATE_FIXATION_OF_RIGHTS",
        "חשב קיבוע": "CALCULATE_FIXATION_OF_RIGHTS",
        "חשב קיבוע זכויות": "CALCULATE_FIXATION_OF_RIGHTS",
        "חישוב קיבוע": "CALCULATE_FIXATION_OF_RIGHTS",
        "חישוב קיבוע זכויות": "CALCULATE_FIXATION_OF_RIGHTS",
    }
    mapped = hebrew_map.get(lowered)
    if mapped:
        return mapped

    return tool_name


def _extract_single_line_json_after_marker(reply: str, marker: str) -> dict[str, Any]:
    if marker not in reply:
        raise ValueError(f"Missing marker: {marker}")

    after = reply.split(marker, 1)[1].strip()
    json_str = after.strip("`").strip()
    json_str = json_str.splitlines()[0] if json_str else ""
    if not json_str:
        raise json.JSONDecodeError(f"Empty JSON after {marker}", after, 0)

    parsed = json.loads(json_str)
    if not isinstance(parsed, dict):
        raise ValueError(f"Expected object JSON after {marker}")
    return parsed


def validate_tool_call_protocol_for_execution(reply: str) -> tuple[bool, str | None]:
    """Server-side enforcement for the mandatory pre-tool protocol.

    Only call this when you are about to execute a tool.
    """

    if "###TOOL_CALL###" not in (reply or ""):
        return True, None

    if "###APPROVAL_REQUIRED###" in reply:
        approval_payload = None
        try:
            approval_payload = _extract_single_line_json_after_marker(
                reply, "###APPROVAL_REQUIRED###"
            )
        except Exception:
            approval_payload = None

        reason = None
        if isinstance(approval_payload, dict):
            try:
                reason = str(approval_payload.get("reason") or "").strip() or None
            except Exception:
                reason = None

        msg = (
            "ERROR: TOOL_CALL blocked (Approval Step). The model indicated approval is required.\n"
            + (f"reason: {reason}\n" if reason else "")
            + "details: reply contained ###APPROVAL_REQUIRED###\n"
        )
        return False, msg

    idx_tool = reply.find("###TOOL_CALL###")
    idx_transparency = reply.find("###TRANSPARENCY_LOG###")
    idx_risk = reply.find("###RISK_REVIEW###")

    missing: list[str] = []
    if idx_transparency < 0:
        missing.append("###TRANSPARENCY_LOG###")
    if idx_risk < 0:
        missing.append("###RISK_REVIEW###")
    if missing:
        return (
            False,
            "ERROR: TOOL_CALL blocked (Approval Step). Missing required sections: "
            + ", ".join(missing)
            + ".",
        )

    if not (idx_transparency < idx_risk < idx_tool):
        return (
            False,
            "ERROR: TOOL_CALL blocked (Approval Step). Required sections are out of order. "
            "Expected: ###TRANSPARENCY_LOG### then ###RISK_REVIEW### then ###TOOL_CALL###.",
        )

    try:
        _ = _extract_single_line_json_after_marker(reply, "###TRANSPARENCY_LOG###")
    except Exception as e:
        return (
            False,
            "ERROR: TOOL_CALL blocked (Approval Step). Invalid or missing JSON after ###TRANSPARENCY_LOG###. "
            + f"Details: {type(e).__name__}: {e}",
        )

    try:
        risk = _extract_single_line_json_after_marker(reply, "###RISK_REVIEW###")
    except Exception as e:
        return (
            False,
            "ERROR: TOOL_CALL blocked (Approval Step). Invalid or missing JSON after ###RISK_REVIEW###. "
            + f"Details: {type(e).__name__}: {e}",
        )

    approval_required = False
    conflict_with_rag = False
    try:
        approval_required = bool(risk.get("approval_required"))
    except Exception:
        approval_required = False
    try:
        conflict_with_rag = bool(risk.get("conflict_with_rag"))
    except Exception:
        conflict_with_rag = False

    if approval_required or conflict_with_rag:
        return (
            False,
            "ERROR: TOOL_CALL blocked (Approval Step). Risk Review requires approval or indicates conflict with RAG. "
            f"approval_required={approval_required}, conflict_with_rag={conflict_with_rag}.",
        )

    return True, None


def parse_tool_call_from_reply(reply: str) -> tuple[str, dict[str, Any]] | None:
    marker = "###TOOL_CALL###"
    if marker not in reply:
        return None

    parts = reply.split(marker)
    if len(parts) <= 1:
        return None

    text_part = parts[0].strip()
    tool_part = parts[1].strip()

    tool_json_str = tool_part.strip("`").strip()
    if not tool_json_str:
        return None

    tool_json_str = tool_json_str.splitlines()[0]
    try:
        tool_data = json.loads(tool_json_str)
    except json.JSONDecodeError:
        return None

    return text_part, tool_data


def apply_max_exemption_if_requested(
    tool_name: str | None, tool_args: dict[str, Any], force_max_exemption: bool
) -> None:
    if force_max_exemption and tool_name == "RUN_RETIREMENT_CASHFLOW_ANALYSIS":
        tool_args["apply_max_exemption"] = True


def build_tool_call_message_content(tool_data: dict[str, Any], ensure_ascii: bool) -> str:
    return f"###TOOL_CALL### {json.dumps(tool_data, ensure_ascii=ensure_ascii)}"


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


def format_tool_output_for_user_stream(tool_name: str, tool_result: str) -> str:
    if not isinstance(tool_name, str) or not tool_name:
        return tool_result

    if isinstance(tool_result, str) and tool_result.strip().lower().startswith("error:"):
        return tool_result

    if tool_name in {
        "CALCULATE_CAPITAL_WITHDRAWAL_TAX",
        "CALCULATE_TAX_SPREAD_BENEFIT",
        "CALCULATE_TAX_EXEMPT_PENSION",
        "PROCESS_TERMINATION",
        "EXECUTE_PENSION_COMMUTATION",
    }:
        raw = tool_result or ""
        severance_reset_suffix = ""
        if tool_name == "PROCESS_TERMINATION":
            marker = "###SEVERANCE_RESET###"
            end_marker = "###END_SEVERANCE_RESET###"
            if marker in raw and end_marker in raw:
                start_idx = raw.find(marker)
                end_idx = raw.find(end_marker)
                if start_idx >= 0 and end_idx >= start_idx:
                    severance_reset_suffix = raw[start_idx : end_idx + len(end_marker)]
                    raw = raw[:start_idx].strip()

        try:
            parsed = json.loads(raw)
        except Exception:
            return tool_result

        if tool_name == "CALCULATE_CAPITAL_WITHDRAWAL_TAX" and isinstance(parsed, dict):
            gross = parsed.get("withdrawal_amount_gross")
            tax_amount = parsed.get("tax_amount")
            net_amount = parsed.get("net_amount")
            eff_rate = parsed.get("effective_tax_rate")
            year = parsed.get("withdrawal_year")

            lines: list[str] = []
            lines.append("חישוב מס על משיכת הון – סיכום:")
            if gross is not None:
                lines.append(f"• סכום משיכה ברוטו: {float(gross):,.0f} ₪")
            if year is not None:
                lines.append(f"• שנת מס: {int(year)}")
            if tax_amount is not None:
                lines.append(f"• מס משוער: {float(tax_amount):,.0f} ₪")
            if net_amount is not None:
                lines.append(f"• נטו משוער: {float(net_amount):,.0f} ₪")
            if eff_rate is not None:
                lines.append(f"• שיעור מס אפקטיבי: {float(eff_rate):.1f}%")
            return "\n".join(lines)

        if tool_name == "CALCULATE_TAX_SPREAD_BENEFIT" and isinstance(parsed, dict):
            gross_amount = parsed.get("gross_amount")
            spread_years = parsed.get("spread_years")
            immediate_tax = parsed.get("immediate_tax")
            spread_total_tax = parsed.get("spread_total_tax")
            tax_benefit = parsed.get("tax_benefit")
            immediate_net = parsed.get("immediate_net")
            spread_net = parsed.get("spread_net")

            lines = []
            lines.append("ניתוח הטבת מס בפריסה – סיכום:")
            if gross_amount is not None:
                lines.append(f"• סכום חייב שנבדק: {float(gross_amount):,.0f} ₪")
            if spread_years is not None:
                lines.append(f"• שנות פריסה: {int(spread_years)}")
            if immediate_tax is not None:
                lines.append(f"• מס מיידי (ללא פריסה): {float(immediate_tax):,.0f} ₪")
            if immediate_net is not None:
                lines.append(f"• נטו מיידי (ללא פריסה): {float(immediate_net):,.0f} ₪")
            if spread_total_tax is not None:
                lines.append(f"• מס כולל בפריסה: {float(spread_total_tax):,.0f} ₪")
            if spread_net is not None:
                lines.append(f"• נטו לאחר פריסה: {float(spread_net):,.0f} ₪")
            if tax_benefit is not None:
                lines.append(f"• חיסכון מס בפריסה (השוואה): {float(tax_benefit):,.0f} ₪")
            return "\n".join(lines)

        if tool_name == "CALCULATE_TAX_EXEMPT_PENSION" and isinstance(parsed, dict):
            result = parsed.get("result") if isinstance(parsed.get("result"), dict) else parsed
            if not isinstance(result, dict):
                return tool_result

            initial_exempt = result.get("initial_exempt_pension")
            final_exempt = result.get("final_exempt_pension")
            grant_used = result.get("exempt_grant_used")
            monthly_loss = result.get("monthly_pension_loss")

            lines = []
            lines.append("השפעת משיכת מענק פטור על הקצבה הפטורה – סיכום:")
            if grant_used is not None:
                lines.append(f"• מענק פטור שנלקח בחשבון: {float(grant_used):,.0f} ₪")
            if initial_exempt is not None:
                lines.append(f"• קצבה פטורה לפני קיזוז: {float(initial_exempt):,.0f} ₪/חודש")
            if final_exempt is not None:
                lines.append(f"• קצבה פטורה אחרי קיזוז: {float(final_exempt):,.0f} ₪/חודש")
            if monthly_loss is not None:
                lines.append(f"• ירידה חודשית בקצבה הפטורה: {float(monthly_loss):,.0f} ₪/חודש")
            return "\n".join(lines)

        if tool_name == "PROCESS_TERMINATION" and isinstance(parsed, dict):
            success = parsed.get("success")
            message = parsed.get("message")
            details = parsed.get("details") if isinstance(parsed.get("details"), dict) else {}
            already_processed = bool(details.get("already_processed")) or (
                isinstance(message, str) and ("כבר בוצע" in message or "כבר בוצעה" in message)
            )
            termination_date = details.get("termination_date")
            severance_amount = details.get("severance_amount")
            exempt_amount = details.get("exempt_amount")
            taxable_amount = details.get("taxable_amount")
            exempt_choice = details.get("exempt_choice")
            taxable_choice = details.get("taxable_choice")
            annuity_projection = (
                parsed.get("annuity_projection")
                if isinstance(parsed.get("annuity_projection"), dict)
                else {}
            )

            lines = []
            lines.append("סיום עבודה – סיכום ביצוע:")
            if already_processed:
                lines.append("• סטטוס: כבר בוצע בעבר (לא בוצעו שינויים)")
            elif success is not None:
                lines.append(f"• סטטוס: {'בוצע בהצלחה' if bool(success) else 'נכשל'}")
            if isinstance(message, str) and message.strip():
                lines.append(f"• הודעה: {message.strip()}")
            if termination_date is not None:
                lines.append(f"• תאריך סיום עבודה (במערכת): {termination_date}")

            if severance_amount is not None:
                try:
                    lines.append(f"• סה\"כ פיצויים שטופלו: {float(severance_amount):,.0f} ₪")
                except Exception:
                    lines.append(f"• סה\"כ פיצויים שטופלו: {severance_amount} ₪")
            if exempt_amount is not None or exempt_choice is not None:
                parts: list[str] = []
                if exempt_amount is not None:
                    try:
                        parts.append(f"{float(exempt_amount):,.0f} ₪")
                    except Exception:
                        parts.append(f"{exempt_amount} ₪")
                if isinstance(exempt_choice, str) and exempt_choice:
                    parts.append(f"בחירה: {exempt_choice}")
                if parts:
                    lines.append("• מענק פטור: " + " | ".join(parts))
            if taxable_amount is not None or taxable_choice is not None:
                parts = []
                if taxable_amount is not None:
                    try:
                        parts.append(f"{float(taxable_amount):,.0f} ₪")
                    except Exception:
                        parts.append(f"{taxable_amount} ₪")
                if isinstance(taxable_choice, str) and taxable_choice:
                    parts.append(f"בחירה: {taxable_choice}")
                if parts:
                    lines.append("• מענק חייב: " + " | ".join(parts))

            if isinstance(annuity_projection, dict) and annuity_projection:
                total_monthly = annuity_projection.get("total_monthly_annuity")
                total_deposit = annuity_projection.get("total_annuity_deposit")
                if total_monthly is not None:
                    try:
                        lines.append(
                            f"• תוספת קצבה מהחלק החייב (משוער): {float(total_monthly):,.0f} ₪/חודש"
                        )
                    except Exception:
                        lines.append(
                            f"• תוספת קצבה מהחלק החייב (משוער): {total_monthly} ₪/חודש"
                        )
                if total_deposit is not None:
                    try:
                        lines.append(
                            f"• הפקדה כוללת שהומרה לקצבה: {float(total_deposit):,.0f} ₪"
                        )
                    except Exception:
                        lines.append(f"• הפקדה כוללת שהומרה לקצבה: {total_deposit} ₪")
                details_list = annuity_projection.get("details")
                if isinstance(details_list, list) and details_list:
                    lines.append("• פירוט לפי תכנית:")
                    for item in details_list:
                        if not isinstance(item, dict):
                            continue
                        plan_name = item.get("plan_name")
                        monthly = item.get("monthly_annuity")
                        deposit = item.get("deposit")
                        coeff = item.get("coefficient")
                        try:
                            plan_parts = []
                            if isinstance(plan_name, str) and plan_name.strip():
                                plan_parts.append(plan_name.strip())
                            if deposit is not None:
                                plan_parts.append(f"הפקדה {float(deposit):,.0f} ₪")
                            if coeff is not None:
                                plan_parts.append(f"מקדם {float(coeff):,.2f}")
                            if monthly is not None:
                                plan_parts.append(f"קצבה {float(monthly):,.0f} ₪/חודש")
                            if plan_parts:
                                lines.append("  - " + " | ".join(plan_parts))
                        except Exception:
                            continue

            created_pension_id = parsed.get("created_pension_id")
            created_capital_asset_id = parsed.get("created_capital_asset_id")
            if created_pension_id is not None:
                lines.append(f"• מזהה קצבה שנוצרה/עודכנה: {created_pension_id}")
            if created_capital_asset_id is not None:
                lines.append(f"• מזהה נכס הון שנוצר/עודכן: {created_capital_asset_id}")
            summary = "\n".join(lines)
            return summary + (severance_reset_suffix or "")

        if tool_name == "EXECUTE_PENSION_COMMUTATION" and isinstance(parsed, dict):
            if parsed.get("success") is False:
                msg = parsed.get("message") or parsed.get("error")
                return f"שגיאה בביצוע היוון: {msg}" if msg else tool_result

            lines = []
            lines.append("✅ ביצוע היוון קצבה – בוצע בהצלחה")
            if parsed.get("pension_fund_id") is not None:
                lines.append(f"• מזהה קצבה: {parsed.get('pension_fund_id')}")
            if parsed.get("commutation_asset_id") is not None:
                lines.append(f"• מזהה נכס היוון: {parsed.get('commutation_asset_id')}")
            if parsed.get("commutation_amount") is not None:
                try:
                    lines.append(f"• סכום היוון: {float(parsed.get('commutation_amount')):,.0f} ₪")
                except Exception:
                    lines.append(f"• סכום היוון: {parsed.get('commutation_amount')} ₪")
            if parsed.get("commutation_date"):
                lines.append(f"• תאריך: {parsed.get('commutation_date')}")
            if parsed.get("tax_treatment"):
                lines.append(f"• יחס מס: {parsed.get('tax_treatment')}")
            if parsed.get("new_balance") is not None:
                try:
                    lines.append(f"• יתרה חדשה בקצבה: {float(parsed.get('new_balance')):,.0f} ₪")
                except Exception:
                    lines.append(f"• יתרה חדשה בקצבה: {parsed.get('new_balance')} ₪")
            if parsed.get("new_pension_amount") is not None:
                try:
                    lines.append(f"• קצבה חודשית חדשה: {float(parsed.get('new_pension_amount')):,.0f} ₪")
                except Exception:
                    lines.append(f"• קצבה חודשית חדשה: {parsed.get('new_pension_amount')} ₪")
            return "\n".join(lines)

        return tool_result

    if tool_name in {"GENERATE_FULL_REPORT", "GENERATE_TAX_DEDUCTION_DOCUMENTS"}:
        try:
            parsed_doc = json.loads(tool_result)
        except Exception:
            return tool_result
        if not isinstance(parsed_doc, dict):
            return tool_result

        status_message = parsed_doc.get("status_message") or parsed_doc.get("message")
        open_path = parsed_doc.get("open_path")
        download_url = parsed_doc.get("download_url")

        lines: list[str] = []
        if isinstance(status_message, str) and status_message.strip():
            lines.append(status_message.strip())
        if isinstance(open_path, str) and open_path.strip():
            lines.append(f"open_path: {open_path.strip()}")
        if isinstance(download_url, str) and download_url.strip():
            lines.append(f"download_url: {download_url.strip()}")
        return "\n".join(lines) if lines else tool_result

    if tool_name == "CALCULATE_FIXATION_OF_RIGHTS":
        try:
            parsed_fix = json.loads(tool_result)
        except Exception:
            return tool_result
        if not isinstance(parsed_fix, dict):
            return tool_result
        if parsed_fix.get("success") is False:
            msg = parsed_fix.get("message") or parsed_fix.get("error")
            return f"שגיאה בחישוב קיבוע זכויות: {msg}" if msg else tool_result

        lines: list[str] = []
        lines.append("קיבוע זכויות – סיכום:")
        if parsed_fix.get("fixation_id") is not None:
            lines.append(f"• מזהה קיבוע: {parsed_fix.get('fixation_id')}")
        if parsed_fix.get("eligibility_year") is not None:
            lines.append(f"• שנת קיבוע: {parsed_fix.get('eligibility_year')}")
        if parsed_fix.get("monthly_exempt_pension") is not None:
            try:
                lines.append(f"• קצבה פטורה חודשית: {float(parsed_fix.get('monthly_exempt_pension')):,.2f} ₪")
            except Exception:
                lines.append(f"• קצבה פטורה חודשית: {parsed_fix.get('monthly_exempt_pension')} ₪")
        if parsed_fix.get("exempt_pension_percentage") is not None:
            try:
                lines.append(f"• אחוז קצבה פטורה: {float(parsed_fix.get('exempt_pension_percentage'))*100:.2f}%")
            except Exception:
                lines.append(f"• אחוז קצבה פטורה: {parsed_fix.get('exempt_pension_percentage')}")
        if parsed_fix.get("exempt_capital_initial") is not None:
            try:
                lines.append(f"• הון פטור ראשוני: {float(parsed_fix.get('exempt_capital_initial')):,.2f} ₪")
            except Exception:
                lines.append(f"• הון פטור ראשוני: {parsed_fix.get('exempt_capital_initial')} ₪")
        return "\n".join(lines)

    if tool_name == "SUBMIT_TAX_COMMUTATION":
        try:
            parsed_submit = json.loads(tool_result)
        except Exception:
            return tool_result
        if not isinstance(parsed_submit, dict):
            return tool_result
        if parsed_submit.get("success") is False:
            msg = parsed_submit.get("message") or parsed_submit.get("error")
            return f"שגיאה בביצוע: {msg}" if msg else tool_result
        lines: list[str] = []
        lines.append("✅ ביצוע קיבוע/היוון/פריסה – בוצע בהצלחה")
        if parsed_submit.get("commutation_type"):
            lines.append(f"• סוג פעולה: {parsed_submit.get('commutation_type')}")
        if parsed_submit.get("submission_id"):
            lines.append(f"• מזהה הגשה: {parsed_submit.get('submission_id')}")
        if parsed_submit.get("final_net_amount") is not None:
            try:
                lines.append(f"• נטו מאושר לתיעוד: {float(parsed_submit.get('final_net_amount')):,.0f} ₪")
            except Exception:
                lines.append(f"• נטו מאושר לתיעוד: {parsed_submit.get('final_net_amount')} ₪")
        return "\n".join(lines)

    if tool_name == "EXECUTE_PENSION_COMMUTATION":
        try:
            parsed_exec = json.loads(tool_result)
        except Exception:
            return tool_result
        if not isinstance(parsed_exec, dict):
            return tool_result
        if parsed_exec.get("success") is False:
            msg = parsed_exec.get("message") or parsed_exec.get("error")
            return f"שגיאה בביצוע היוון: {msg}" if msg else tool_result

        lines: list[str] = []
        lines.append("✅ ביצוע היוון קצבה – בוצע בהצלחה")
        if parsed_exec.get("pension_fund_id") is not None:
            lines.append(f"• מזהה קצבה: {parsed_exec.get('pension_fund_id')}")
        if parsed_exec.get("commutation_asset_id") is not None:
            lines.append(f"• מזהה נכס היוון: {parsed_exec.get('commutation_asset_id')}")
        if parsed_exec.get("commutation_amount") is not None:
            try:
                lines.append(f"• סכום היוון: {float(parsed_exec.get('commutation_amount')):,.0f} ₪")
            except Exception:
                lines.append(f"• סכום היוון: {parsed_exec.get('commutation_amount')} ₪")
        if parsed_exec.get("commutation_date"):
            lines.append(f"• תאריך: {parsed_exec.get('commutation_date')}")
        if parsed_exec.get("tax_treatment"):
            lines.append(f"• יחס מס: {parsed_exec.get('tax_treatment')}")
        if parsed_exec.get("new_balance") is not None:
            try:
                lines.append(f"• יתרה חדשה בקצבה: {float(parsed_exec.get('new_balance')):,.0f} ₪")
            except Exception:
                lines.append(f"• יתרה חדשה בקצבה: {parsed_exec.get('new_balance')} ₪")
        if parsed_exec.get("new_pension_amount") is not None:
            try:
                lines.append(f"• קצבה חודשית חדשה: {float(parsed_exec.get('new_pension_amount')):,.0f} ₪")
            except Exception:
                lines.append(f"• קצבה חודשית חדשה: {parsed_exec.get('new_pension_amount')} ₪")
        return "\n".join(lines)

    try:
        data = json.loads(tool_result)
        gross = data.get("total_guaranteed_income") or data.get("projected_pension")
        net = data.get("total_guaranteed_income_net") or data.get("projected_pension_net")
        income_tax = data.get("monthly_income_tax")
        total_tax = data.get("monthly_tax_deduction")
        exempt_pct = data.get("exemption_percentage")
        exempt_amount = data.get("exempt_pension_monthly")
        liquid_capital = data.get("total_liquid_capital")
        suff_years = data.get("capital_sufficiency_years")
        is_sustainable = data.get("is_sustainable")

        lines: list[str] = []
        lines.append("ניתוח פרישה – עיקרי התוצאות (חודשיות):")
        if gross is not None:
            lines.append(f"• קצבה ברוטו: {gross:,.0f} ₪")
        if income_tax is not None or total_tax is not None:
            tax_to_show = income_tax if income_tax is not None else total_tax
            if tax_to_show is not None:
                lines.append(f"• מס הכנסה חודשי על הקצבה: {tax_to_show:,.0f} ₪")
        if net is not None:
            lines.append(f"• קצבה נטו לאחר מס: {net:,.0f} ₪")
        if exempt_pct is not None or exempt_amount is not None:
            extra_parts: list[str] = []
            if exempt_pct is not None:
                extra_parts.append(f"אחוז קצבה פטורה: {exempt_pct:.1f}%")
            if exempt_amount is not None:
                extra_parts.append(f"סכום קצבה פטורה חודשי: {exempt_amount:,.0f} ₪")
            if extra_parts:
                lines.append("• פטור מקסימלי מקיבוע זכויות: " + " | ".join(extra_parts))

        if liquid_capital is not None:
            lines.append(f"• הון נזיל זמין לתכנון: {liquid_capital:,.0f} ₪")
        if suff_years is not None:
            try:
                lines.append(f"• קיימות כספית (שנים): {float(suff_years):g}")
            except Exception:
                lines.append(f"• קיימות כספית (שנים): {suff_years}")
        if is_sustainable is not None:
            lines.append(f"• בר-קיימא: {'כן' if bool(is_sustainable) else 'לא'}")

        return "\n".join(lines)

    except Exception:
        return tool_result


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
    has_numeric = bool(re.search(r"\b\d{2,3}\s*[kK]\b", lowered)) or bool(
        re.search(r"\b\d{4,6}\b", lowered)
    ) or ("אלף" in lowered)
    return has_numeric


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
        "בחודש",
        "חודש",
        "הכנסה",
        "צריך",
        "זקוק",
        "יעד",
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
        near = lowered_clean[max(0, start - 14) : min(len(lowered_clean), start + 14)]
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

    triggers = [
        "תזרים",
        "cashflow",
        "קצבה",
        "פנסיה",
        "פרישה",
        "גיל פרישה",
        "תאריך פרישה",
        "השווא",
        "לעומת",
        "מול",
        "תרחיש",
        "גובה הקצבה",
        "משוך קצבה",
        "להתחיל קצבה",
        "קיבוע",
        "פטור",
        "ברוטו",
        "מס",
    ]

    return any(t in lowered for t in triggers)


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


def build_portfolio_wide_prev_employers_severance_transform_accounts_from_portfolio(
    *,
    pension_portfolio: Any,
    conversion_type: str,
) -> list[dict[str, Any]]:
    fields = ["פיצויים_ממעסיקים_קודמים_רצף_קצבה"]
    if not isinstance(pension_portfolio, list) or not pension_portfolio:
        return []

    derived = build_transform_accounts_from_portfolio(pension_portfolio)
    if not derived:
        return []

    results: list[dict[str, Any]] = []
    for acc in derived:
        if not isinstance(acc, dict):
            continue

        component_fields = [
            "פיצויים_מעסיק_נוכחי",
            "פיצויים_לאחר_התחשבנות",
            "פיצויים_שלא_עברו_התחשבנות",
            "פיצויים_ממעסיקים_קודמים_רצף_זכויות",
            "פיצויים_ממעסיקים_קודמים_רצף_קצבה",
            "תגמולי_עובד_עד_2000",
            "תגמולי_עובד_אחרי_2000",
            "תגמולי_עובד_אחרי_2008_לא_משלמת",
            "תגמולי_מעביד_עד_2000",
            "תגמולי_מעביד_אחרי_2000",
            "תגמולי_מעביד_אחרי_2008_לא_משלמת",
            "תגמולים",
            "סך_תגמולים",
            "קרן_השתלמות",
        ]

        specific_amounts = acc.get("specific_amounts") if isinstance(acc.get("specific_amounts"), dict) else {}

        selected: dict[str, float] = {}
        total = 0.0
        for f in fields:
            raw = None
            if isinstance(specific_amounts, dict):
                raw = specific_amounts.get(f)
            if raw is None:
                raw = acc.get(f)
            try:
                val = float(raw or 0)
            except Exception:
                val = 0.0
            if val > 0:
                selected[f] = float(val)
                total += float(val)

        if not selected:
            continue

        base = dict(acc)
        for k in component_fields:
            if k not in selected:
                base.pop(k, None)
        base["_partial_conversion"] = True
        base["specific_amounts"] = selected
        base["component_conversion_overrides"] = {f: str(conversion_type or "pension") for f in selected.keys()}
        try:
            base["balance"] = float(total)
            base["יתרה"] = float(total)
        except Exception:
            pass
        results.append(base)

    return results


def build_portfolio_wide_education_fund_transform_accounts_from_portfolio(
    *,
    pension_portfolio: Any,
    conversion_type: str,
) -> list[dict[str, Any]]:
    fields = ["קרן_השתלמות"]
    if not isinstance(pension_portfolio, list) or not pension_portfolio:
        return []

    derived = build_transform_accounts_from_portfolio(pension_portfolio)
    if not derived:
        return []

    results: list[dict[str, Any]] = []
    for acc in derived:
        if not isinstance(acc, dict):
            continue

        product_type = str(acc.get("product_type") or acc.get("סוג_מוצר") or "")
        account_name = str(acc.get("account_name") or acc.get("שם_תכנית") or "")
        candidate = f"{product_type} {account_name}".lower()

        if ("השתלמות" not in candidate) and ("education" not in candidate) and ("klal_stud" not in candidate):
            continue

        specific_amounts = acc.get("specific_amounts") if isinstance(acc.get("specific_amounts"), dict) else {}
        try:
            ef_val = float(specific_amounts.get("קרן_השתלמות") or acc.get("קרן_השתלמות") or 0)
        except Exception:
            ef_val = 0.0
        if ef_val <= 0:
            continue

        selected: dict[str, float] = {}
        total = 0.0
        for f in fields:
            raw = None
            if isinstance(specific_amounts, dict):
                raw = specific_amounts.get(f)
            if raw is None:
                raw = acc.get(f)
            try:
                val = float(raw or 0)
            except Exception:
                val = 0.0
            if val > 0:
                selected[f] = float(val)
                total += float(val)

        if not selected:
            continue

        component_fields = [
            "פיצויים_מעסיק_נוכחי",
            "פיצויים_לאחר_התחשבנות",
            "פיצויים_שלא_עברו_התחשבנות",
            "פיצויים_ממעסיקים_קודמים_רצף_זכויות",
            "פיצויים_ממעסיקים_קודמים_רצף_קצבה",
            "תגמולי_עובד_עד_2000",
            "תגמולי_עובד_אחרי_2000",
            "תגמולי_עובד_אחרי_2008_לא_משלמת",
            "תגמולי_מעביד_עד_2000",
            "תגמולי_מעביד_אחרי_2000",
            "תגמולי_מעביד_אחרי_2008_לא_משלמת",
            "תגמולים",
            "סך_תגמולים",
            "קרן_השתלמות",
        ]

        base = dict(acc)
        for k in component_fields:
            if k not in selected:
                base.pop(k, None)
        base["_partial_conversion"] = True
        base["specific_amounts"] = selected
        base["component_conversion_overrides"] = {f: str(conversion_type or "capital_asset") for f in selected.keys()}
        try:
            base["balance"] = float(total)
            base["יתרה"] = float(total)
        except Exception:
            pass
        results.append(base)

    return results


def build_portfolio_wide_after_settlement_severance_transform_accounts_from_portfolio(
    *,
    pension_portfolio: Any,
    conversion_type: str,
) -> list[dict[str, Any]]:
    fields = ["פיצויים_לאחר_התחשבנות"]
    if not isinstance(pension_portfolio, list) or not pension_portfolio:
        return []

    derived = build_transform_accounts_from_portfolio(pension_portfolio)
    if not derived:
        return []

    results: list[dict[str, Any]] = []
    for acc in derived:
        if not isinstance(acc, dict):
            continue

        product_type = str(acc.get("product_type") or acc.get("סוג_מוצר") or "")
        account_name = str(acc.get("account_name") or acc.get("שם_תכנית") or "")
        candidate = f"{product_type} {account_name}".lower()
        if "השתלמות" in candidate or "education" in candidate:
            continue

        specific_amounts = acc.get("specific_amounts") if isinstance(acc.get("specific_amounts"), dict) else {}
        try:
            ef_val = float(specific_amounts.get("קרן_השתלמות") or acc.get("קרן_השתלמות") or 0)
        except Exception:
            ef_val = 0.0
        if ef_val > 0:
            continue

        selected: dict[str, float] = {}
        total = 0.0
        for f in fields:
            raw = None
            if isinstance(specific_amounts, dict):
                raw = specific_amounts.get(f)
            if raw is None:
                raw = acc.get(f)
            try:
                val = float(raw or 0)
            except Exception:
                val = 0.0
            if val > 0:
                selected[f] = float(val)
                total += float(val)

        if not selected:
            continue

        component_fields = [
            "פיצויים_מעסיק_נוכחי",
            "פיצויים_לאחר_התחשבנות",
            "פיצויים_שלא_עברו_התחשבנות",
            "פיצויים_ממעסיקים_קודמים_רצף_זכויות",
            "פיצויים_ממעסיקים_קודמים_רצף_קצבה",
            "תגמולי_עובד_עד_2000",
            "תגמולי_עובד_אחרי_2000",
            "תגמולי_עובד_אחרי_2008_לא_משלמת",
            "תגמולי_מעביד_עד_2000",
            "תגמולי_מעביד_אחרי_2000",
            "תגמולי_מעביד_אחרי_2008_לא_משלמת",
            "תגמולים",
            "סך_תגמולים",
            "קרן_השתלמות",
        ]

        base = dict(acc)
        for k in component_fields:
            if k not in selected:
                base.pop(k, None)
        base["_partial_conversion"] = True
        base["specific_amounts"] = selected
        base["component_conversion_overrides"] = {f: str(conversion_type or "capital_asset") for f in selected.keys()}
        try:
            base["balance"] = float(total)
            base["יתרה"] = float(total)
        except Exception:
            pass
        results.append(base)

    return results


def sanitize_user_visible_text(text: str) -> str:
    if not isinstance(text, str) or not text:
        return text
    updated = text

    def _strip_marker_block(raw: str, marker: str) -> str:
        if marker not in raw:
            return raw
        lines = raw.splitlines()
        out: list[str] = []
        skip_next_json = False
        for line in lines:
            if line.strip() == marker:
                skip_next_json = True
                continue
            if skip_next_json:
                stripped = line.strip()
                if stripped.startswith("{") and stripped.endswith("}"):
                    skip_next_json = False
                    continue
                if stripped:
                    skip_next_json = False
            out.append(line)
        return "\n".join(out)

    updated = _strip_marker_block(updated, "###TRANSPARENCY_LOG###")
    updated = _strip_marker_block(updated, "###RISK_REVIEW###")

    # Also support inline single-line markers (common in non-stream agent replies), e.g.:
    # ###TRANSPARENCY_LOG### {"action": "..."}
    # ###RISK_REVIEW### {"approval_required": false}
    try:
        updated = re.sub(
            r"^\s*###TRANSPARENCY_LOG###\s*\{.*\}\s*$",
            "",
            updated,
            flags=re.MULTILINE,
        )
    except Exception:
        pass
    try:
        updated = re.sub(
            r"^\s*###RISK_REVIEW###\s*\{.*\}\s*$",
            "",
            updated,
            flags=re.MULTILINE,
        )
    except Exception:
        pass

    try:
        updated = re.sub(
            r"\n?###TARGET_PENSION_PLAN_DATA###.*?###END_TARGET_PENSION_PLAN_DATA###\n?",
            "\n",
            updated,
            flags=re.DOTALL,
        )
    except Exception:
        pass

    lowered_preview = updated.lower()
    has_llm_thought_sections = any(
        token in lowered_preview
        for token in (
            "context check",
            "risk analysis",
            "action/decision",
            "הקונטקסט ובדיקת סבירות",
            "ניתוח סיכונים",
            "החלטה/צעדים",
        )
    )
    if has_llm_thought_sections:
        cut_tokens = [
            "context check",
            "risk analysis",
            "action/decision",
            "הקונטקסט ובדיקת סבירות",
            "ניתוח סיכונים",
            "החלטה/צעדים",
        ]
        cut_idx = None
        lowered_current = updated.lower()
        for tok in cut_tokens:
            idx_tok = lowered_current.find(tok)
            if idx_tok >= 0:
                cut_idx = idx_tok if cut_idx is None else min(cut_idx, idx_tok)
        if cut_idx is not None and cut_idx >= 0:
            updated = updated[:cut_idx].rstrip()
        idx = updated.find("##")
        if idx >= 0:
            updated = updated[idx:].lstrip()

    updated = re.sub(r"^\s*צריכת\s+מודל.*$", "", updated, flags=re.MULTILINE)
    updated = re.sub(r"^\s*[A-Z0-9_]+_HANDLER_VERSION=.*$", "", updated, flags=re.MULTILINE)
    updated = re.sub(r"\n{3,}", "\n\n", updated).strip()

    updated = updated.replace("PROCESS_TERMINATION", "עזיבת עבודה")
    updated = updated.replace("process_termination", "עזיבת עבודה")

    ids_in_order = re.findall(r"תרחיש\s+מזהה\s+(\d{1,9})", updated)
    if ids_in_order:
        mapping: dict[str, int] = {}
        next_idx = 1
        for sid in ids_in_order:
            if sid not in mapping:
                mapping[sid] = next_idx
                next_idx += 1

        def _replace_scenario_identifier(m: re.Match) -> str:
            sid = str(m.group(1))
            idx = mapping.get(sid, 0)
            if idx <= 0:
                return m.group(0)
            return f"תרחיש {idx}"

        updated = re.sub(
            r"תרחיש\s+מזהה\s+(\d{1,9})",
            _replace_scenario_identifier,
            updated,
        )

    return updated


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
    has_explicit_termination_intent = any(k in lowered for k in explicit_termination_keywords)
    if not has_explicit_termination_intent:
        has_convert_verb = ("המר" in lowered) or ("המרה" in lowered) or ("להמיר" in lowered) or ("convert" in lowered)
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

    if any(
        token in lowered
        for token in (
            "אל תשתמש",
            "לא להשתמש",
            "אל תבצע",
            "לא לבצע",
            "בלי",
            "ללא",
            "ביקשתי שלא",
        )
    ):
        if any(
            token in lowered
            for token in (
                "process_termination",
                "process termination",
                "termination",
                "סיום עבודה",
                "עזיבת עבודה",
            )
        ):
            return False

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

    return any(a in lowered for a in action_tokens) and any(d in lowered for d in domain_tokens)


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

    return any(t in lowered for t in change_tokens) and any(d in lowered for d in domain_tokens)


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

    return is_retirement_cashflow_request(user_message)


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
        if any(k in lowered for k in ("משוך", "משיכה", "למשוך", "משוך את כל", "כל התיק", "כל הסכומים", "100%")):
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
    has_need_phrase = any(k in lowered for k in ["צריך קצבה", "זקוק לקצבה", "זקוקה לקצבה", "אני צריך קצבה", "אני זקוק לקצבה"])
    has_numeric_target = bool(re.search(r"\b\d{2,3}\s*k\b", lowered)) or bool(re.search(r"\b\d{4,6}\b", lowered))
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


def build_transform_accounts_from_portfolio(pension_portfolio: Any) -> list[dict[str, Any]]:
    if not isinstance(pension_portfolio, list) or not pension_portfolio:
        return []

    def _extract_account_number(data: dict[str, Any]) -> Any:
        if not isinstance(data, dict):
            return None
        return (
            data.get("מספר_חשבון")
            or data.get("מספר חשבון")
            or data.get("account_number")
            or data.get("מספר חשבון")
            or data.get("מספר-חשבון")
        )

    def _coerce_float(value: Any) -> float:
        if value is None:
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return 0.0
            cleaned = raw.replace(",", "").replace("₪", "").replace(" ", "")
            try:
                return float(cleaned)
            except (TypeError, ValueError):
                return 0.0
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def item_to_dict(item: Any) -> dict[str, Any]:
        if isinstance(item, dict):
            return item
        model_dump = getattr(item, "model_dump", None)
        if callable(model_dump):
            dumped = model_dump()
            return dumped if isinstance(dumped, dict) else {}
        raw = getattr(item, "__dict__", {})
        return raw if isinstance(raw, dict) else {}

    component_fields = [
        "פיצויים_מעסיק_נוכחי",
        "פיצויים_לאחר_התחשבנות",
        "פיצויים_שלא_עברו_התחשבנות",
        "פיצויים_ממעסיקים_קודמים_רצף_זכויות",
        "פיצויים_ממעסיקים_קודמים_רצף_קצבה",
        "תגמולי_עובד_עד_2000",
        "תגמולי_עובד_אחרי_2000",
        "תגמולי_עובד_אחרי_2008_לא_משלמת",
        "תגמולי_מעביד_עד_2000",
        "תגמולי_מעביד_אחרי_2000",
        "תגמולי_מעביד_אחרי_2008_לא_משלמת",
        "תגמולים",
        "קרן_השתלמות",
    ]

    accounts: list[dict[str, Any]] = []
    for item in pension_portfolio:
        data = item_to_dict(item)

        nested_specific = data.get("specific_amounts")
        if not isinstance(nested_specific, dict):
            nested_specific = {}

        account_number = _extract_account_number(data)
        account_name = data.get("שם_תכנית")
        company = data.get("חברה_מנהלת")
        product_type = data.get("סוג_מוצר")
        balance = data.get("יתרה")
        start_date = data.get("תאריך_התחלה")

        specific_amounts: dict[str, float] = {}
        for field in component_fields:
            value = data.get(field)
            if value is None and field in nested_specific:
                value = nested_specific.get(field)
            numeric = _coerce_float(value)
            if numeric > 0:
                specific_amounts[field] = numeric

        accounts.append(
            {
                "account_number": account_number,
                "account_name": account_name,
                "company": company,
                "product_type": product_type,
                "balance": balance,
                "start_date": start_date,
                "specific_amounts": specific_amounts,
                "מספר_חשבון": account_number,
                "מספר חשבון": account_number,
                "שם_תכנית": account_name,
                "חברה_מנהלת": company,
                "סוג_מוצר": product_type,
                "יתרה": balance,
                "תאריך_התחלה": start_date,
                **{field: data.get(field) for field in component_fields if field in data},
            }
        )

    return accounts


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


def build_portfolio_wide_component_transform_accounts_from_portfolio(
    *,
    pension_portfolio: Any,
    fields: list[str],
    conversion_type: str,
) -> list[dict[str, Any]]:
    if not fields:
        return []
    if not isinstance(pension_portfolio, list) or not pension_portfolio:
        return []

    derived = build_transform_accounts_from_portfolio(pension_portfolio)
    if not derived:
        return []

    results: list[dict[str, Any]] = []
    for acc in derived:
        if not isinstance(acc, dict):
            continue

        product_type = str(acc.get("product_type") or acc.get("סוג_מוצר") or "")
        account_name = str(acc.get("account_name") or acc.get("שם_תכנית") or "")
        candidate = f"{product_type} {account_name}".lower()

        # Exclude education funds from portfolio-wide 'tagmulim after 2000' conversion.
        # These products are capital-like and converting them here looks like a full-portfolio conversion.
        if "השתלמות" in candidate or "education" in candidate:
            continue

        specific_amounts = acc.get("specific_amounts") if isinstance(acc.get("specific_amounts"), dict) else {}
        try:
            ef_val = float(specific_amounts.get("קרן_השתלמות") or acc.get("קרן_השתלמות") or 0)
        except Exception:
            ef_val = 0.0
        if ef_val > 0:
            continue

        selected: dict[str, float] = {}
        total = 0.0
        for f in fields:
            raw = None
            if isinstance(specific_amounts, dict):
                raw = specific_amounts.get(f)
            if raw is None:
                raw = acc.get(f)
            try:
                val = float(raw or 0)
            except Exception:
                val = 0.0
            if val > 0:
                selected[f] = float(val)
                total += float(val)

        if not selected:
            continue

        component_fields = [
            "פיצויים_מעסיק_נוכחי",
            "פיצויים_לאחר_התחשבנות",
            "פיצויים_שלא_עברו_התחשבנות",
            "פיצויים_ממעסיקים_קודמים_רצף_זכויות",
            "פיצויים_ממעסיקים_קודמים_רצף_קצבה",
            "תגמולי_עובד_עד_2000",
            "תגמולי_עובד_אחרי_2000",
            "תגמולי_עובד_אחרי_2008_לא_משלמת",
            "תגמולי_מעביד_עד_2000",
            "תגמולי_מעביד_אחרי_2000",
            "תגמולי_מעביד_אחרי_2008_לא_משלמת",
            "תגמולים",
            "סך_תגמולים",
            "קרן_השתלמות",
        ]

        base = dict(acc)
        for k in component_fields:
            if k not in selected:
                base.pop(k, None)
        base["_partial_conversion"] = True
        base["specific_amounts"] = selected
        base["component_conversion_overrides"] = {f: str(conversion_type or "pension") for f in selected.keys()}
        try:
            base["balance"] = float(total)
            base["יתרה"] = float(total)
        except Exception:
            pass
        results.append(base)

    return results


def build_partial_pension_transform_accounts_from_portfolio(
    *,
    pension_portfolio: Any,
    account_number: str,
    amount: float,
) -> list[dict[str, Any]]:
    if not account_number:
        return []
    try:
        amount_val = float(amount or 0)
    except Exception:
        amount_val = 0.0
    if amount_val <= 0:
        return []
    if not isinstance(pension_portfolio, list) or not pension_portfolio:
        return []

    matched = None
    for item in pension_portfolio:
        if not isinstance(item, dict):
            model_dump = getattr(item, "model_dump", None)
            if callable(model_dump):
                try:
                    item = model_dump()
                except Exception:
                    item = None
        if not isinstance(item, dict):
            continue
        num = str(item.get("מספר_חשבון") or item.get("account_number") or item.get("מספר חשבון") or "").strip()
        if num == str(account_number).strip():
            matched = item
            break

    if not isinstance(matched, dict):
        return []

    derived = build_transform_accounts_from_portfolio([matched])
    if not derived:
        return []

    acc = dict(derived[0])
    component_fields = [
        "פיצויים_מעסיק_נוכחי",
        "פיצויים_לאחר_התחשבנות",
        "פיצויים_שלא_עברו_התחשבנות",
        "פיצויים_ממעסיקים_קודמים_רצף_זכויות",
        "פיצויים_ממעסיקים_קודמים_רצף_קצבה",
        "תגמולי_עובד_עד_2000",
        "תגמולי_עובד_אחרי_2000",
        "תגמולי_עובד_אחרי_2008_לא_משלמת",
        "תגמולי_מעביד_עד_2000",
        "תגמולי_מעביד_אחרי_2000",
        "תגמולי_מעביד_אחרי_2008_לא_משלמת",
        "תגמולים",
        "סך_תגמולים",
        "קרן_השתלמות",
    ]
    for k in component_fields:
        acc.pop(k, None)
    acc["_partial_conversion"] = True
    acc["specific_amounts"] = {"תגמולים": float(amount_val)}
    acc["component_conversion_overrides"] = {"תגמולים": "pension"}
    try:
        acc["balance"] = float(amount_val)
        acc["יתרה"] = float(amount_val)
    except Exception:
        pass
    return [acc]


def build_targeted_component_transform_accounts_from_portfolio(
    *,
    pension_portfolio: Any,
    account_number: str,
    fields: list[str],
    conversion_type: str,
) -> list[dict[str, Any]]:
    if not account_number or not fields:
        return []
    if not isinstance(pension_portfolio, list) or not pension_portfolio:
        return []

    matched = None
    for item in pension_portfolio:
        if not isinstance(item, dict):
            model_dump = getattr(item, "model_dump", None)
            if callable(model_dump):
                try:
                    item = model_dump()
                except Exception:
                    item = None
        if not isinstance(item, dict):
            continue
        num = str(item.get("מספר_חשבון") or item.get("account_number") or item.get("מספר חשבון") or "").strip()
        if num == str(account_number).strip():
            matched = item
            break

    if not isinstance(matched, dict):
        return []

    derived = build_transform_accounts_from_portfolio([matched])
    if not derived:
        return []

    base = dict(derived[0])
    specific_amounts = base.get("specific_amounts") if isinstance(base.get("specific_amounts"), dict) else {}
    selected: dict[str, float] = {}
    total = 0.0
    for f in fields:
        raw = None
        if isinstance(specific_amounts, dict):
            raw = specific_amounts.get(f)
        if raw is None:
            raw = base.get(f)
        try:
            val = float(raw or 0)
        except Exception:
            val = 0.0
        if val > 0:
            selected[f] = float(val)
            total += float(val)

    if not selected:
        return []

    component_fields = [
        "פיצויים_מעסיק_נוכחי",
        "פיצויים_לאחר_התחשבנות",
        "פיצויים_שלא_עברו_התחשבנות",
        "פיצויים_ממעסיקים_קודמים_רצף_זכויות",
        "פיצויים_ממעסיקים_קודמים_רצף_קצבה",
        "תגמולי_עובד_עד_2000",
        "תגמולי_עובד_אחרי_2000",
        "תגמולי_עובד_אחרי_2008_לא_משלמת",
        "תגמולי_מעביד_עד_2000",
        "תגמולי_מעביד_אחרי_2000",
        "תגמולי_מעביד_אחרי_2008_לא_משלמת",
        "תגמולים",
        "סך_תגמולים",
        "קרן_השתלמות",
    ]
    for k in component_fields:
        if k not in selected:
            base.pop(k, None)
    base["_partial_conversion"] = True
    base["specific_amounts"] = selected
    base["component_conversion_overrides"] = {f: str(conversion_type or "pension") for f in selected.keys()}
    try:
        base["balance"] = float(total)
        base["יתרה"] = float(total)
    except Exception:
        pass

    return [base]


def is_no_tools_request(user_message: str) -> bool:
    if not user_message:
        return False

    lowered = user_message.lower()

    triggers = [
        "אין להריץ שום כלי",
        "אין להריץ כלים",
        "לא להריץ שום כלי",
        "לא להפעיל כלים",
        "בלי כלים",
        "ללא כלים",
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
