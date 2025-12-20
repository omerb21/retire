from ...schemas.llm_chat import PensionPortfolioAccount


def _as_float(value) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _get_attr_float(acc: PensionPortfolioAccount, name: str) -> float:
    return _as_float(getattr(acc, name, 0) or 0)


def _is_education_fund(product_type: str) -> bool:
    return "השתלמות" in (product_type or "").lower()


def _is_investment_provident_fund(product_type: str) -> bool:
    return "גמל להשקעה" in (product_type or "").lower()


def _is_regular_provident_fund(product_type: str) -> bool:
    lowered = (product_type or "").lower()
    return ("קופת גמל" in lowered) and ("להשקעה" not in lowered)


def _is_pension_or_insurance(product_type: str) -> bool:
    lowered = (product_type or "").lower()
    return ("קרן פנסיה" in lowered) or ("פנסיה" in lowered) or ("ביטוח" in lowered)


def _format_snapshot_at(snapshot_at: str | None) -> str:
    raw = (snapshot_at or "").strip()
    if not raw:
        return ""
    return raw.replace("T", " ").replace("Z", "")


def _detect_requested_split(user_message: str | None) -> str:
    lowered = (user_message or "").lower()

    if any(k in lowered for k in ["פיצויים", "תגמולים", "פיצויים/תגמולים"]):
        return "components"
    if any(k in lowered for k in ["חברה", "חברה מנהלת", "לפי חברה"]):
        return "company"
    if any(k in lowered for k in ["סוג מוצר", "סוג המוצר", "לפי מוצר", "לפי סוג"]):
        return "product_type"
    if any(k in lowered for k in ["הון", "קצבה", "הון/קצבה", "קצבתי", "הוני"]):
        return "capital_pension"
    return "overview"


def build_pension_portfolio_context(
    portfolio: list[PensionPortfolioAccount],
    user_message: str | None = None,
    snapshot_at: str | None = None,
) -> list[str]:
    if not portfolio:
        return []

    context_lines: list[str] = []
    context_lines.append("")
    context_lines.append("📂 **תיק פנסיוני (נתונים גולמיים מקובץ מסלקה)**")
    formatted_snapshot = _format_snapshot_at(snapshot_at)
    if formatted_snapshot:
        context_lines.append(f"🕒 **הנתונים נכונים לתאריך snapshot:** {formatted_snapshot}")
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
    blocked_accounts: list[dict] = []
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

        has_detailed_tagmulim = (
            tagmul_emp_to_2000
            + tagmul_emp_after_2000
            + tagmul_emp_after_2008_np
            + tagmul_empr_to_2000
            + tagmul_empr_after_2000
            + tagmul_empr_after_2008_np
        ) > 0

        # If we only have aggregate tagmulim fields (תגמולים/סך_תגמולים) and no detailed breakdown,
        # classify them using conversion rules (not by column heuristics).
        if tagmulim_total > 0 and not has_detailed_tagmulim:
            if _is_education_fund(product_type) or _is_regular_provident_fund(product_type) or _is_investment_provident_fund(product_type):
                capital_sum += tagmulim_total
            elif _is_pension_or_insurance(product_type):
                pension_sum += tagmulim_total
            else:
                unspecified_sum += tagmulim_total

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

        # Conversion-rule override: Education fund is always capital, regardless of column composition.
        if _is_education_fund(product_type):
            capital_sum = capital_sum + pension_sum + unspecified_sum
            pension_sum = 0.0
            unspecified_sum = 0.0

        blocked_sum = severance_not_settled + severance_prev_rights
        if blocked_sum > 0:
            blocked_accounts.append(
                {
                    "name": acc.שם_תכנית or "ללא שם",
                    "type": product_type,
                    "company": acc.חברה_מנהלת or "",
                    "account_number": account_number,
                    "severance_not_settled": severance_not_settled,
                    "severance_prev_rights": severance_prev_rights,
                    "blocked_sum": blocked_sum,
                }
            )

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
                "capital_classified": capital_sum,
                "pension_classified": pension_sum,
                "blocked_classified": unspecified_sum,
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
        context_lines.append("🚫 **חשוב מאוד – יתרות חסומות שאי אפשר לטפל בהן במערכת:**")
        context_lines.append(
            "המערכת והסוכן *לא יכולים* לבצע המרה/משיכה/חישוב מס סופי על רכיבים אלה. "
            "נדרש טיפול חיצוני מול הגוף המנהל/מעסיקים (התחשבנות/השלמת רצפים) ורק לאחר מכן אפשר להמשיך במערכת."
        )
        if has_unsettled_severance:
            context_lines.append(
                "- קיימות יתרות ב־'פיצויים שלא עברו התחשבנות' (חסום להמרה עד התחשבנות)."
            )
        if has_rights_sequence:
            context_lines.append(
                "- קיימות יתרות ב־'רצף זכויות (פיצויים ממעסיקים קודמים)' (חסום לטיפול במערכת)."
            )
        if blocked_accounts:
            blocked_sorted = sorted(blocked_accounts, key=lambda x: float(x.get("blocked_sum") or 0), reverse=True)
            context_lines.append("")
            context_lines.append("**פירוט חשבונות עם יתרות חסומות (פורמט קריא):**")
            for b in blocked_sorted[:15]:
                context_lines.append(f"- תכנית: {(b.get('name') or '')[:60]}")
                context_lines.append(f"  סוג מוצר: {(b.get('type') or '')[:60]}")
                context_lines.append(f"  חברה מנהלת: {(b.get('company') or '')[:60]}")
                context_lines.append(
                    f"  חסום: לא התחשבנות: {float(b.get('severance_not_settled') or 0):,.0f} ₪"
                )
                context_lines.append(
                    f"  חסום: רצף זכויות: {float(b.get('severance_prev_rights') or 0):,.0f} ₪"
                )
                context_lines.append(f"  סה\"כ חסום: {float(b.get('blocked_sum') or 0):,.0f} ₪")
                if b.get("account_number"):
                    context_lines.append(f"  מספר חשבון: {b.get('account_number')}")
                context_lines.append("")
        context_lines.append("")

    requested_split = _detect_requested_split(user_message)

    context_lines.append("## סיכום מהיר")
    context_lines.append("**סיכום נתונים גולמיים:**")
    context_lines.append(f"  • סה\"כ יתרות: {total_balance:,.0f} ₪")
    if total_capital_by_columns > 0 or total_pension_by_columns > 0 or total_unspecified_by_columns > 0:
        context_lines.append(
            "  • חלוקה דטרמיניסטית (לפי עמודות + חריגים לפי חוקי המרה/קרן השתלמות):"
        )
        if total_pension_by_columns > 0:
            context_lines.append(f"    ◦ סכומים קצבתיים: {total_pension_by_columns:,.0f} ₪")
        if total_capital_by_columns > 0:
            context_lines.append(f"    ◦ סכומים הוניים: {total_capital_by_columns:,.0f} ₪")
        if total_unspecified_by_columns > 0:
            context_lines.append(f"    ◦ סכומים לא מסווגים/חסומים (לא התחשבנות/רצף זכויות): {total_unspecified_by_columns:,.0f} ₪")

    if requested_split == "components":
        context_lines.append("")
        context_lines.append("## חלוקה לפי רכיבים (פיצויים/תגמולים)")
    elif requested_split == "company":
        context_lines.append("")
        context_lines.append("## חלוקה לפי חברה מנהלת")
    elif requested_split == "product_type":
        context_lines.append("")
        context_lines.append("## חלוקה לפי סוג מוצר")
    elif requested_split == "capital_pension":
        context_lines.append("")
        context_lines.append("## חלוקה לפי הון/קצבה/חסום")
    else:
        context_lines.append("")
        context_lines.append("## מוצרים מובילים לפי יתרה")
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

    if requested_split in ("company", "product_type"):
        grouped: dict[str, dict] = {}
        group_key = "company" if requested_split == "company" else "type"
        for p in products_list:
            key = (p.get(group_key) or "לא ידוע").strip() or "לא ידוע"
            row = grouped.get(key)
            if row is None:
                row = {
                    "count": 0,
                    "balance": 0.0,
                    "capital": 0.0,
                    "pension": 0.0,
                    "blocked": 0.0,
                }
                grouped[key] = row
            row["count"] += 1
            row["balance"] += float(p.get("balance") or 0)
            row["capital"] += float(p.get("capital_classified") or 0)
            row["pension"] += float(p.get("pension_classified") or 0)
            row["blocked"] += float(p.get("blocked_classified") or 0)

        rows = sorted(grouped.items(), key=lambda kv: float(kv[1].get("balance") or 0), reverse=True)
        context_lines.append("**סיכום לפי קבוצה (פורמט קריא):**")
        for k, r in rows:
            context_lines.append(f"- קבוצה: {k[:60]}")
            context_lines.append(f"  מספר חשבונות: {int(r['count'])}")
            context_lines.append(f"  יתרה: {float(r['balance']):,.0f} ₪")
            context_lines.append(f"  הון: {float(r['capital']):,.0f} ₪")
            context_lines.append(f"  קצבה: {float(r['pension']):,.0f} ₪")
            context_lines.append(f"  חסום: {float(r['blocked']):,.0f} ₪")
            context_lines.append("")

    if requested_split == "capital_pension":
        context_lines.append("**חלוקה לפי הון/קצבה/חסום (פורמט קריא):**")
        rows = sorted(products_list, key=lambda p: float(p.get("balance") or 0), reverse=True)
        for p in rows[:25]:
            context_lines.append(f"- תכנית: {(p.get('name') or '')[:60]}")
            context_lines.append(f"  סוג מוצר: {(p.get('type') or '')[:60]}")
            if p.get("company"):
                context_lines.append(f"  חברה מנהלת: {(p.get('company') or '')[:60]}")
            context_lines.append(f"  יתרה: {float(p.get('balance') or 0):,.0f} ₪")
            context_lines.append(f"  הון: {float(p.get('capital_classified') or 0):,.0f} ₪")
            context_lines.append(f"  קצבה: {float(p.get('pension_classified') or 0):,.0f} ₪")
            context_lines.append(f"  חסום/לא מסווג: {float(p.get('blocked_classified') or 0):,.0f} ₪")
            if p.get("account_number"):
                context_lines.append(f"  מספר חשבון: {p.get('account_number')}")
            if p.get("start_date"):
                context_lines.append(f"  תאריך התחלה: {p.get('start_date')}")
            context_lines.append("")

    if requested_split == "overview":
        rows = sorted(products_list, key=lambda p: float(p.get("balance") or 0), reverse=True)
        context_lines.append("**מוצרים מובילים לפי יתרה (פורמט קריא):**")
        for p in rows[:15]:
            context_lines.append(f"- תכנית: {(p.get('name') or '')[:60]}")
            context_lines.append(f"  סוג מוצר: {(p.get('type') or '')[:60]}")
            if p.get("company"):
                context_lines.append(f"  חברה מנהלת: {(p.get('company') or '')[:60]}")
            context_lines.append(f"  יתרה: {float(p.get('balance') or 0):,.0f} ₪")
            if p.get("account_number"):
                context_lines.append(f"  מספר חשבון: {p.get('account_number')}")
            context_lines.append("")

    if canonical_accounts:
        context_lines.append("")
        context_lines.append("🔑 **מזהים לחשבונות (למניעת כפילויות בהמרה):**")
        for a in canonical_accounts[:30]:
            context_lines.append(f"- תכנית: {(a.get('account_name') or '')[:60]}")
            if a.get("account_number"):
                context_lines.append(f"  מספר חשבון: {a.get('account_number')}")
            if a.get("start_date"):
                context_lines.append(f"  תאריך התחלה: {a.get('start_date')}")
            context_lines.append("")

    context_lines.append("")
    context_lines.append("🔧 **לקבלת קצבה מחושבת:** הפעל BUILD_TARGET_PENSION_PLAN עם יעד קצבה (למשל 20000)")
    context_lines.append("   הכלי יחזיר מקדמים אמיתיים לפי גיל, מין וסוג מוצר.")

    return context_lines
