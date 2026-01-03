import json


def format_transform_result_for_user(*, tool_result: str) -> str:
    try:
        parsed = json.loads(tool_result)
    except Exception:
        return "בוצעה המרה, אך לא הצלחתי לקרוא את תוצאת הכלי."

    if not isinstance(parsed, dict):
        return "בוצעה המרה, אך תוצאת הכלי אינה בפורמט צפוי."

    if parsed.get("success") is not True:
        err = parsed.get("error") or "המרה נכשלה."
        return f"המרה נכשלה: {err}"

    total_converted = int(parsed.get("total_converted") or 0)
    converted_pensions = int(parsed.get("converted_pensions") or 0)
    converted_capitals = int(parsed.get("converted_capitals") or 0)
    converted_commutations = int(parsed.get("converted_commutations") or 0)

    ignored_blocked_amount = parsed.get("ignored_blocked_amount")
    employer_current_sev = parsed.get("employer_current_severance_not_converted")

    converted_items = parsed.get("converted_items")
    if not isinstance(converted_items, list):
        converted_items = []

    skipped_items = parsed.get("skipped_items")
    if not isinstance(skipped_items, list):
        skipped_items = []

    lines: list[str] = []
    lines.append("סיכום המרה הון/קצבה בתיק:")
    lines.append(f"הומרו {total_converted} חשבונות")
    lines.append(f"נכסי קצבה שנוצרו/עודכנו: {converted_pensions}")
    lines.append(f"נכסי הון שנוצרו/עודכנו: {converted_capitals}")
    if converted_commutations:
        lines.append(f"מתוכם היוון להון (רכיבים קצבתיים): {converted_commutations}")

    if ignored_blocked_amount is not None:
        try:
            lines.append(
                f"יתרות חסומות שדולגו לפי הבקשה: {float(ignored_blocked_amount):,.0f} ₪"
            )
        except Exception:
            lines.append(f"יתרות חסומות שדולגו לפי הבקשה: {ignored_blocked_amount}")

    if employer_current_sev is not None:
        try:
            lines.append(
                f"פיצויי מעסיק נוכחי שלא הומרו (חסימה מערכתית): {float(employer_current_sev):,.0f} ₪"
            )
        except Exception:
            lines.append(
                f"פיצויי מעסיק נוכחי שלא הומרו (חסימה מערכתית): {employer_current_sev}"
            )

    errors = parsed.get("errors")
    if isinstance(errors, list) and errors:
        lines.append("הערות/שגיאות במהלך ההמרה:")
        for item in errors[:5]:
            lines.append(f"- {item}")

    def _format_amount(value: object) -> str:
        try:
            return f"{float(value or 0):,.0f}"
        except Exception:
            return str(value)

    def _format_tax(value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            return ""
        mapping = {
            "exempt": "פטור",
            "taxable": "חייב",
            "capital_gains": "רווח הון",
            "tax_spread": "פריסת מס",
            "fixed_rate": "שיעור קבוע",
        }
        return mapping.get(value, value)

    if converted_items:
        lines.append("\nפירוט חשבונות שהומרו:")

        for it in converted_items[:20]:
            if not isinstance(it, dict):
                continue
            kind = it.get("kind")
            kind_label = "נכס" if kind else "פריט"
            if kind == "pension":
                kind_label = "יתרה שהומרה לקצבה"
            elif kind == "capital_asset":
                kind_label = "יתרה שהומרה להון"
            elif kind == "commutation":
                kind_label = "יתרה שהוּונה להון"

            account_name = it.get("account_name") or ""
            account_number = it.get("account_number") or ""
            amount = _format_amount(it.get("amount"))
            tax_label = _format_tax(it.get("tax_treatment"))

            header = f"- {account_name} ({account_number}) — {kind_label}: {amount} ₪"
            if tax_label:
                header += f" — מס: {tax_label}"
            lines.append(header)

            components = it.get("components")
            if isinstance(components, dict) and components:
                shown = 0
                for field, val in components.items():
                    try:
                        num_val = float(val or 0)
                    except Exception:
                        num_val = 0.0
                    if num_val <= 0:
                        continue
                    lines.append(f"  - {field}: {_format_amount(num_val)} ₪")
                    shown += 1
                    if shown >= 10:
                        break

        if len(converted_items) > 20:
            lines.append(f"(הוצגו 20 מתוך {len(converted_items)} חשבונות שהומרו)")

    if skipped_items:
        lines.append("\nרכיבים/חשבונות שדולגו:")
        for it in skipped_items[:15]:
            if not isinstance(it, dict):
                continue
            acc_name = it.get("account_name") or ""
            acc_num = it.get("account_number") or ""
            field = it.get("field") or ""
            amount = _format_amount(it.get("amount"))
            reason = it.get("reason") or ""
            line = f"- {acc_name} ({acc_num}) — {field}: {amount} ₪"
            if reason:
                line += f" — {reason}"
            lines.append(line)

        if len(skipped_items) > 15:
            lines.append(f"(הוצגו 15 מתוך {len(skipped_items)} פריטים שדולגו)")

    return "\n".join(lines)
