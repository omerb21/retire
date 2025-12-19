from ...schemas.llm_chat import PensionPortfolioAccount


def _as_float(value) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _get_attr_float(acc: PensionPortfolioAccount, name: str) -> float:
    return _as_float(getattr(acc, name, 0) or 0)


def build_pension_portfolio_context(portfolio: list[PensionPortfolioAccount]) -> list[str]:
    if not portfolio:
        return []

    context_lines: list[str] = []
    context_lines.append("")
    context_lines.append("📂 **תיק פנסיוני (נתונים גולמיים מקובץ מסלקה)**")
    context_lines.append("⚠️ **חובה:** להפעיל BUILD_TARGET_PENSION_PLAN לקבלת קצבה מחושבת עם מקדמים אמיתיים!")
    context_lines.append("")

    total_balance = 0.0
    totals = {
        "severance_current_employer": 0.0,
        "severance_after_settlement": 0.0,
        "severance_not_settled": 0.0,
        "severance_prev_employers_sequence_rights": 0.0,
        "severance_prev_employers_sequence_pension": 0.0,
        "tagmulim_employee_to_2000": 0.0,
        "tagmulim_employee_after_2000": 0.0,
        "tagmulim_employee_after_2008_non_paying": 0.0,
        "tagmulim_employer_to_2000": 0.0,
        "tagmulim_employer_after_2000": 0.0,
        "tagmulim_employer_after_2008_non_paying": 0.0,
        "tagmulim_total": 0.0,
    }

    has_unsettled_severance = False
    has_rights_sequence = False
    products_list: list[dict] = []
    canonical_accounts: list[dict] = []

    total_capital_by_columns = 0.0
    total_pension_by_columns = 0.0
    total_unspecified_by_columns = 0.0

    for acc in portfolio:
        balance = _as_float(getattr(acc, "יתרה", 0))
        if balance <= 0:
            continue

        total_balance += balance

        severance_current = _get_attr_float(acc, "פיצויים_מעסיק_נוכחי")
        severance_after_settlement = _get_attr_float(acc, "פיצויים_לאחר_התחשבנות")
        severance_not_settled = _get_attr_float(acc, "פיצויים_שלא_עברו_התחשבנות")
        severance_prev_rights = _get_attr_float(acc, "פיצויים_ממעסיקים_קודמים_רצף_זכויות")
        severance_prev_pension = _get_attr_float(acc, "פיצויים_ממעסיקים_קודמים_רצף_קצבה")

        totals["severance_current_employer"] += severance_current
        totals["severance_after_settlement"] += severance_after_settlement
        totals["severance_not_settled"] += severance_not_settled
        totals["severance_prev_employers_sequence_rights"] += severance_prev_rights
        totals["severance_prev_employers_sequence_pension"] += severance_prev_pension

        if severance_not_settled > 0:
            has_unsettled_severance = True
        if severance_prev_rights > 0:
            has_rights_sequence = True

        tagmul_emp_to_2000 = _get_attr_float(acc, "תגמולי_עובד_עד_2000")
        tagmul_emp_after_2000 = _get_attr_float(acc, "תגמולי_עובד_אחרי_2000")
        tagmul_emp_after_2008_np = _get_attr_float(acc, "תגמולי_עובד_אחרי_2008_לא_משלמת")
        tagmul_empr_to_2000 = _get_attr_float(acc, "תגמולי_מעביד_עד_2000")
        tagmul_empr_after_2000 = _get_attr_float(acc, "תגמולי_מעביד_אחרי_2000")
        tagmul_empr_after_2008_np = _get_attr_float(acc, "תגמולי_מעביד_אחרי_2008_לא_משלמת")

        tagmulim_total = _as_float(getattr(acc, "סך_תגמולים", None) or getattr(acc, "תגמולים", None))
        if tagmulim_total <= 0:
            tagmulim_total = (
                tagmul_emp_to_2000
                + tagmul_emp_after_2000
                + tagmul_emp_after_2008_np
                + tagmul_empr_to_2000
                + tagmul_empr_after_2000
                + tagmul_empr_after_2008_np
            )

        totals["tagmulim_employee_to_2000"] += tagmul_emp_to_2000
        totals["tagmulim_employee_after_2000"] += tagmul_emp_after_2000
        totals["tagmulim_employee_after_2008_non_paying"] += tagmul_emp_after_2008_np
        totals["tagmulim_employer_to_2000"] += tagmul_empr_to_2000
        totals["tagmulim_employer_after_2000"] += tagmul_empr_after_2000
        totals["tagmulim_employer_after_2008_non_paying"] += tagmul_empr_after_2008_np
        totals["tagmulim_total"] += tagmulim_total

        product_type = acc.סוג_מוצר or "לא ידוע"
        product_lower = product_type.lower()

        account_number = (acc.מספר_חשבון or "").strip() or None
        start_date = (acc.תאריך_התחלה or "").strip() or None

        is_capital_only = False
        is_capital_candidate = False
        is_pension_candidate = False
        is_unspecified_candidate = False

        capital_sum = 0.0
        pension_sum = 0.0
        unspecified_sum = 0.0

        capital_sum += severance_current + severance_after_settlement
        pension_sum += severance_prev_pension
        unspecified_sum += severance_not_settled + severance_prev_rights

        if tagmul_emp_after_2000 > 0:
            pension_sum += tagmul_emp_after_2000
        if tagmul_empr_after_2000 > 0:
            pension_sum += tagmul_empr_after_2000

        pension_sum += tagmul_emp_after_2008_np + tagmul_empr_after_2008_np
        capital_sum += tagmul_emp_to_2000 + tagmul_empr_to_2000

        if "השתלמות" in product_lower:
            is_capital_only = True
            category = "הון בלבד"
        elif "גמל להשקעה" in product_lower:
            is_capital_only = True
            category = "הון (ניתן להמרה)"
        else:
            if pension_sum > 0 and capital_sum == 0:
                category = "קצבתי"
            elif capital_sum > 0 and pension_sum == 0:
                category = "הוני"
            elif pension_sum > 0 and capital_sum > 0:
                category = "קצבתי/הוני"
            else:
                category = "לא מסווג"

        total_cols = capital_sum + pension_sum + unspecified_sum
        if total_cols > 0:
            if capital_sum == 0 and pension_sum == 0:
                is_unspecified_candidate = True
            elif pension_sum >= capital_sum:
                is_pension_candidate = True
            else:
                is_capital_candidate = True

        total_capital_by_columns += capital_sum
        total_pension_by_columns += pension_sum
        total_unspecified_by_columns += unspecified_sum

        products_list.append(
            {
                "name": acc.שם_תכנית or "ללא שם",
                "company": acc.חברה_מנהלת or "",
                "type": product_type,
                "category": category,
                "balance": balance,
                "account_number": account_number,
                "start_date": start_date,
                "severance_current": severance_current,
                "severance_after_settlement": severance_after_settlement,
                "severance_not_settled": severance_not_settled,
                "severance_prev_rights": severance_prev_rights,
                "severance_prev_pension": severance_prev_pension,
                "severance_total": (
                    severance_current
                    + severance_after_settlement
                    + severance_not_settled
                    + severance_prev_rights
                    + severance_prev_pension
                ),
                "tagmulim_total": tagmulim_total,
                "is_capital_candidate": is_capital_candidate,
                "is_pension_candidate": is_pension_candidate,
                "is_unspecified_candidate": is_unspecified_candidate,
                "is_capital_only": is_capital_only,
            }
        )

        canonical_accounts.append(
            {
                "account_name": acc.שם_תכנית or "",
                "balance": balance,
                "product_type": product_type,
                "company": acc.חברה_מנהלת or "",
                "account_number": account_number,
                "start_date": start_date,
            }
        )

    if has_unsettled_severance or has_rights_sequence:
        context_lines.append("🚫 **אזהרה רגולטורית/תפעולית:**")
        if has_unsettled_severance:
            context_lines.append(
                "  • קיימות יתרות בעמודה 'פיצויים שלא עברו התחשבנות' – אין לבצע תרחישים/המרות עד טיפול והתאפסות העמודה."
            )
        if has_rights_sequence:
            context_lines.append(
                "  • קיימות יתרות בעמודה 'רצף זכויות (פיצויים ממעסיקים קודמים)' – אין לבצע משיכות/מס סופי על כספים אלו ללא טיפול חיצוני."
            )
        context_lines.append("")

    context_lines.append(
        "| מוצר | סוג | סיווג מוצר | יתרה (₪) | פיצויים סה\"כ | תגמולים סה\"כ | דגלים | מספר חשבון |"
    )
    context_lines.append("|------|------|-----------|----------|------------|-------------|--------|------------|")

    for p in products_list:
        flags: list[str] = []
        if float(p.get("severance_not_settled") or 0) > 0:
            flags.append("לא התחשבנות")
        if float(p.get("severance_prev_rights") or 0) > 0:
            flags.append("רצף זכויות")
        if bool(p.get("is_unspecified_candidate")):
            flags.append("לא מסווג")
        elif bool(p.get("is_pension_candidate")):
            flags.append("קצבה")
        elif bool(p.get("is_capital_candidate")):
            flags.append("הון")

        context_lines.append(
            f"| {p['name'][:30]} | {p['type'][:20]} | {p['category']} | {p['balance']:,.0f} | {float(p.get('severance_total') or 0):,.0f} | {float(p.get('tagmulim_total') or 0):,.0f} | {', '.join(flags)} | {p.get('account_number') or ''} |"
        )

    context_lines.append("")
    context_lines.append("**סיכום נתונים גולמיים:**")
    context_lines.append(f"  • סה\"כ יתרות: {total_balance:,.0f} ₪")
    if total_capital_by_columns > 0 or total_pension_by_columns > 0 or total_unspecified_by_columns > 0:
        context_lines.append("  • חלוקה לפי עמודות (דטרמיניסטי, ללא פרשנות לפי שם מוצר):")
        if total_pension_by_columns > 0:
            context_lines.append(f"    ◦ סכומים קצבתיים: {total_pension_by_columns:,.0f} ₪")
        if total_capital_by_columns > 0:
            context_lines.append(f"    ◦ סכומים הוניים: {total_capital_by_columns:,.0f} ₪")
        if total_unspecified_by_columns > 0:
            context_lines.append(f"    ◦ סכומים לא מסווגים/חסומים (לא התחשבנות/רצף זכויות): {total_unspecified_by_columns:,.0f} ₪")
    total_severance = (
        totals["severance_current_employer"]
        + totals["severance_after_settlement"]
        + totals["severance_not_settled"]
        + totals["severance_prev_employers_sequence_rights"]
        + totals["severance_prev_employers_sequence_pension"]
    )
    if total_severance > 0:
        context_lines.append(f"  • סה\"כ פיצויים: {total_severance:,.0f} ₪")
        if totals["severance_current_employer"] > 0:
            context_lines.append(
                f"    ◦ פיצויים מעסיק נוכחי: {totals['severance_current_employer']:,.0f} ₪"
            )
        if totals["severance_after_settlement"] > 0:
            context_lines.append(
                f"    ◦ פיצויים לאחר התחשבנות: {totals['severance_after_settlement']:,.0f} ₪"
            )
        if totals["severance_not_settled"] > 0:
            context_lines.append(
                f"    ◦ פיצויים שלא עברו התחשבנות: {totals['severance_not_settled']:,.0f} ₪"
            )
        if totals["severance_prev_employers_sequence_rights"] > 0:
            context_lines.append(
                f"    ◦ רצף זכויות (מעסיקים קודמים): {totals['severance_prev_employers_sequence_rights']:,.0f} ₪"
            )
        if totals["severance_prev_employers_sequence_pension"] > 0:
            context_lines.append(
                f"    ◦ רצף קצבה (מעסיקים קודמים): {totals['severance_prev_employers_sequence_pension']:,.0f} ₪"
            )

    if totals["tagmulim_total"] > 0:
        context_lines.append(f"  • סה\"כ תגמולים: {totals['tagmulim_total']:,.0f} ₪")
        if totals["tagmulim_employee_to_2000"] + totals["tagmulim_employer_to_2000"] > 0:
            context_lines.append(
                "    ◦ עד 2000 (לרוב הוני/נזיל): "
                f"{(totals['tagmulim_employee_to_2000'] + totals['tagmulim_employer_to_2000']):,.0f} ₪"
            )
        if totals["tagmulim_employee_after_2000"] + totals["tagmulim_employer_after_2000"] > 0:
            context_lines.append(
                "    ◦ אחרי 2000 (לרוב קצבתי/קופת גמל): "
                f"{(totals['tagmulim_employee_after_2000'] + totals['tagmulim_employer_after_2000']):,.0f} ₪"
            )
        if (
            totals["tagmulim_employee_after_2008_non_paying"]
            + totals["tagmulim_employer_after_2008_non_paying"]
            > 0
        ):
            context_lines.append(
                "    ◦ אחרי 2008 (קצבה לא משלמת): "
                f"{(totals['tagmulim_employee_after_2008_non_paying'] + totals['tagmulim_employer_after_2008_non_paying']):,.0f} ₪"
            )

    total_capital_only = sum(p["balance"] for p in products_list if p["is_capital_only"])
    if total_capital_only > 0:
        context_lines.append(f"  • הון שלא ניתן להמרה: {total_capital_only:,.0f} ₪")

    total_unspecified = sum(1 for p in products_list if p.get("is_unspecified_candidate"))
    if total_unspecified > 0:
        context_lines.append(f"  • חשבונות עם רכיבים לא מסווגים/חסומים: {total_unspecified}")

    if canonical_accounts:
        context_lines.append("")
        context_lines.append("🔑 **שדות מזהים (להמרה אידמפוטנטית):**")
        context_lines.append(
            "בעת קריאה לכלי TRANSFORM_FUNDS_TO_ASSETS חובה להעביר לכל חשבון account_number ו-start_date "
            "(מקבילים ל-מספר_חשבון ותאריך_התחלה) כדי למנוע כפילויות ולעדכן רשומות קיימות."
        )
        context_lines.append("")
        context_lines.append("Canonical accounts (keys expected by tools):")
        for a in canonical_accounts:
            context_lines.append(str(a))

    context_lines.append("")
    context_lines.append("🔧 **לקבלת קצבה מחושבת:** הפעל BUILD_TARGET_PENSION_PLAN עם יעד קצבה (למשל 20000)")
    context_lines.append("   הכלי יחזיר מקדמים אמיתיים לפי גיל, מין וסוג מוצר.")

    return context_lines
