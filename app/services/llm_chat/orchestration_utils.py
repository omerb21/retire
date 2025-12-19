import json
from typing import Any


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
        raise json.JSONDecodeError("Empty tool call", tool_part, 0)

    tool_json_str = tool_json_str.splitlines()[0]
    tool_data = json.loads(tool_json_str)

    return text_part, tool_data


def apply_max_exemption_if_requested(
    tool_name: str | None, tool_args: dict[str, Any], force_max_exemption: bool
) -> None:
    if force_max_exemption and tool_name == "RUN_RETIREMENT_CASHFLOW_ANALYSIS":
        tool_args["apply_max_exemption"] = True


def build_tool_call_message_content(tool_data: dict[str, Any], ensure_ascii: bool) -> str:
    return f"###TOOL_CALL### {json.dumps(tool_data, ensure_ascii=ensure_ascii)}"


def build_tool_result_system_message_for_chat(tool_name: str, tool_result: str) -> str:
    return (
        f"🔧 **Tool Result ({tool_name}):**\n"
        f"{tool_result}\n\n"
        "הנחיות למודל: השתמש בנתוני הכלי האלה (ברוטו, נטו, מס, ופרטי פטור אם קיימים) כדי לבנות תשובה אחת סופית וברורה למשתמש על הקצבה נטו אחרי מס. "
        "אל תחזור על ה-JSON הגולמי ואל תיתן תשובה נפרדת רק עבור הכלי עצמו."
    )


def build_tool_result_system_message_for_stream(tool_name: str, tool_result: str) -> str:
    return (
        f"Tool Result ({tool_name}): {tool_result}\n\n"
        "הנחיות למודל: שלב את נתוני הכלי (ברוטו, נטו, מס ופרטי פטור) בתוך תשובה אחת סופית וברורה ללקוח על הקצבה נטו, "
        "ואל תחזור על ה-JSON עצמו כלשונו."
    )


def build_tax_result_system_message_for_chat(tax_result: str) -> str:
    return (
        f"🔧 **Tool Result (GET_TAX_PROJECTION - Auto-chained):**\n{tax_result}\n\n"
        "הנחיות למודל: שלב את תוצאת GET_TAX_PROJECTION (שיעור מס אפקטיבי, מס חודשי וכו') יחד עם נתוני RUN_RETIREMENT_CASHFLOW_ANALYSIS שכבר קיבלת. "
        "עליך להסביר ללקוח קצבה ברוטו, מס, וקצבה נטו, ולהדגיש את השפעת הפטור המקסימלי (אם הופעל) על המס והנטו. אל תחזיר פלט כפול או לא מאוחד."
    )


def build_tax_result_system_message_for_stream(tax_result: str) -> str:
    return (
        f"Tool Result (GET_TAX_PROJECTION): {tax_result}\n\n"
        "הנחיות למודל: שלב את נתוני המס (שיעור מס אפקטיבי, מס חודשי וכו') יחד עם תוצאת ניתוח הפרישה הקודמת, "
        "ונתֵח עבור הלקוח את הקצבה ברוטו, המס והקצבה נטו, תוך הדגשת תרומת הפטור המקסימלי אם הופעל."
    )


def format_tool_output_for_user_stream(tool_name: str, tool_result: str) -> str:
    if tool_name != "RUN_RETIREMENT_CASHFLOW_ANALYSIS":
        return tool_result

    try:
        data = json.loads(tool_result)
        gross = data.get("total_guaranteed_income") or data.get("projected_pension")
        net = data.get("total_guaranteed_income_net") or data.get("projected_pension_net")
        income_tax = data.get("monthly_income_tax")
        total_tax = data.get("monthly_tax_deduction")
        exempt_pct = data.get("exemption_percentage")
        exempt_amount = data.get("exempt_pension_monthly")

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

        return "\n".join(lines)

    except Exception:
        return tool_result


def is_net_pension_request(user_message: str) -> bool:
    net_keywords = ["נטו", "ביד", "אחרי מס", "נקי", "net"]
    message_lower = (user_message or "").lower()
    return any(keyword in message_lower for keyword in net_keywords)


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
    return has_doc_keyword and has_intent_keyword


def is_transform_request(user_message: str) -> bool:
    if not user_message:
        return False

    lowered = user_message.lower()

    triggers = [
        "transform_funds_to_assets",
        "המר",
        "להמיר",
        "המרה",
        "convert",
        "conversion",
        "transform funds",
    ]

    return any(t in lowered for t in triggers)


def is_portfolio_breakdown_request(user_message: str) -> bool:
    if not user_message:
        return False

    lowered = user_message.lower()

    must_have = ["קצבה", "הון"]
    if not all(k in lowered for k in must_have):
        return False

    triggers = [
        "חלוקה",
        "בחלק",
        "כמה",
        "תיק פנסיוני",
        "תיק הפנסיוני",
        "תיק",
        "portfolio",
        "breakdown",
    ]
    return any(t in lowered for t in triggers)


def build_transform_accounts_from_portfolio(pension_portfolio: Any) -> list[dict[str, Any]]:
    if not isinstance(pension_portfolio, list) or not pension_portfolio:
        return []

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

        account_number = data.get("מספר_חשבון")
        account_name = data.get("שם_תכנית")
        company = data.get("חברה_מנהלת")
        product_type = data.get("סוג_מוצר")
        balance = data.get("יתרה")
        start_date = data.get("תאריך_התחלה")

        specific_amounts: dict[str, float] = {}
        for field in component_fields:
            value = data.get(field)
            try:
                numeric = float(value) if value is not None else 0.0
            except (TypeError, ValueError):
                numeric = 0.0
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
                "שם_תכנית": account_name,
                "חברה_מנהלת": company,
                "סוג_מוצר": product_type,
                "יתרה": balance,
                "תאריך_התחלה": start_date,
                **{field: data.get(field) for field in component_fields if field in data},
            }
        )

    return accounts


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
