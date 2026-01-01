import re

from ...schemas.llm_chat import PensionPortfolioAccount

from app.services.pension_portfolio.conversion_rules import (
    COMPONENT_RULES as _SHARED_COMPONENT_RULES,
    FIELD_DISPLAY as _SHARED_FIELD_DISPLAY,
    is_education_fund as _shared_is_education_fund,
    is_investment_provident_fund as _shared_is_investment_provident_fund,
    is_pension_or_insurance as _shared_is_pension_or_insurance,
    is_regular_provident_fund as _shared_is_regular_provident_fund,
    rule_for_tagmulim_by_product_type as _shared_rule_for_tagmulim_by_product_type,
)


def _as_float(value) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _get_attr_float(acc: PensionPortfolioAccount, name: str) -> float:
    return _as_float(getattr(acc, name, 0) or 0)


def _is_education_fund(product_type: str) -> bool:
    return _shared_is_education_fund(product_type)


def _is_investment_provident_fund(product_type: str) -> bool:
    return _shared_is_investment_provident_fund(product_type)


def _is_regular_provident_fund(product_type: str) -> bool:
    return _shared_is_regular_provident_fund(product_type)


def _is_pension_or_insurance(product_type: str) -> bool:
    return _shared_is_pension_or_insurance(product_type)


def _format_snapshot_at(snapshot_at: str | None) -> str:
    raw = (snapshot_at or "").strip()
    if not raw:
        return ""
    return raw.replace("T", " ").replace("Z", "")


def _normalize_start_date_for_display(value: str | None) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None

    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", raw)
    if m:
        return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"

    if re.match(r"^\d{8}$", raw) and (raw.startswith("19") or raw.startswith("20")):
        y = raw[0:4]
        mo = raw[4:6]
        d = raw[6:8]
        return f"{d}/{mo}/{y}"

    if re.match(r"^\d{2}/\d{2}/\d{4}$", raw):
        return raw

    if re.match(r"^\d{2}-\d{2}-\d{4}$", raw):
        return raw.replace("-", "/")

    return raw


_FIELD_DISPLAY: dict[str, str] = dict(_SHARED_FIELD_DISPLAY)


_COMPONENT_RULES: dict[str, dict[str, object]] = dict(_SHARED_COMPONENT_RULES)


def _tax_label(tax: str | None) -> str:
    if tax == "exempt":
        return "פטור ממס"
    if tax == "taxable":
        return "חייב במס"
    if tax == "capital_gains":
        return "חייב במס רווח הון"
    return "לא ידוע"


def _build_conversion_line(*, display: str, amount: float, rule: dict[str, object]) -> list[str]:
    if amount <= 0:
        return []

    can_pension = bool(rule.get("pension"))
    can_capital = bool(rule.get("capital"))
    pension_tax = str(rule.get("pension_tax") or "")
    capital_tax = rule.get("capital_tax")
    capital_tax_str = str(capital_tax) if capital_tax is not None else None

    lines: list[str] = []
    lines.append(f"- {display}: {amount:,.0f} ₪")

    if not can_pension and not can_capital:
        err = str(rule.get("error") or "לא ניתן להמיר")
        lines.append("  סטטוס: חסום במערכת")
        lines.append(f"  סיבה: {err}")
        return lines

    if can_capital:
        lines.append(f"  הון: אפשרי | יחס מס: {_tax_label(capital_tax_str)}")
    else:
        lines.append("  הון: לא אפשרי")

    if can_pension:
        lines.append(f"  קצבה: אפשרי | יחס מס: {_tax_label(pension_tax)}")
    else:
        lines.append("  קצבה: לא אפשרי")

    return lines


def _rule_for_tagmulim_by_product_type(*, product_type: str) -> dict[str, object]:
    return _shared_rule_for_tagmulim_by_product_type(product_type=product_type)


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
    context_lines.append(
        "⚠️ **אזהרה קריטית:** קיום יתרות חסומות בתיק *לא* מונע ניתוח/חישוב/מענה על שאלות לגבי שאר התיק. "
        "פשוט מתייחסים ליתרות החסומות כ'מחוץ לטווח ביצוע' וממשיכים עם כל מה שניתן."
    )
    context_lines.append(
        "ℹ️ **לקצבה מחושבת עם מקדמים אמיתיים:** אפשר להפעיל BUILD_TARGET_PENSION_PLAN *רק* אם המשתמש ביקש במפורש "
        "תכנית ל'יעד קצבה' ונתן יעד חודשי מספרי (למשל 20000). זה *לא חובה* לניתוח טבלת המוצרים/אפשרויות משיכה."
    )
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

    conversion_totals = {k: 0.0 for k in totals.keys()}

    has_unsettled_severance = False
    has_rights_sequence = False
    blocked_accounts: list[dict] = []
    products_list: list[dict] = []
    canonical_accounts: list[dict] = []

    total_capital_by_columns = 0.0
    total_pension_by_columns = 0.0
    total_unspecified_by_columns = 0.0

    tagmulim_aggregate_by_kind: dict[str, float] = {
        "education_fund": 0.0,
        "investment_provident_fund": 0.0,
        "regular_provident_fund": 0.0,
        "pension_or_insurance": 0.0,
        "unknown": 0.0,
    }

    education_fund_total_balance = 0.0
    investment_provident_total_balance = 0.0

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

        is_education = _is_education_fund(product_type)
        is_investment = _is_investment_provident_fund(product_type)

        if _is_education_fund(product_type):
            education_fund_total_balance += balance
        if "גמל להשקעה" in product_lower:
            investment_provident_total_balance += balance

        if not (is_education or is_investment):
            conversion_totals["severance_current_employer"] += severance_current
            conversion_totals["severance_after_settlement"] += severance_after_settlement
            conversion_totals["severance_not_settled"] += severance_not_settled
            conversion_totals["severance_prev_employers_sequence_rights"] += severance_prev_rights
            conversion_totals["severance_prev_employers_sequence_pension"] += severance_prev_pension
            conversion_totals["tagmulim_employee_to_2000"] += tagmul_emp_to_2000
            conversion_totals["tagmulim_employee_after_2000"] += tagmul_emp_after_2000
            conversion_totals["tagmulim_employee_after_2008_non_paying"] += tagmul_emp_after_2008_np
            conversion_totals["tagmulim_employer_to_2000"] += tagmul_empr_to_2000
            conversion_totals["tagmulim_employer_after_2000"] += tagmul_empr_after_2000
            conversion_totals["tagmulim_employer_after_2008_non_paying"] += tagmul_empr_after_2008_np
            conversion_totals["tagmulim_total"] += tagmulim_total

        account_number = (acc.מספר_חשבון or "").strip() or None
        start_date_raw = (acc.תאריך_התחלה or "").strip() or None
        start_date = _normalize_start_date_for_display(start_date_raw)

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
            if _is_education_fund(product_type):
                tagmulim_aggregate_by_kind["education_fund"] += tagmulim_total
            elif _is_investment_provident_fund(product_type):
                tagmulim_aggregate_by_kind["investment_provident_fund"] += tagmulim_total
            elif _is_regular_provident_fund(product_type):
                tagmulim_aggregate_by_kind["regular_provident_fund"] += tagmulim_total
            elif _is_pension_or_insurance(product_type):
                tagmulim_aggregate_by_kind["pension_or_insurance"] += tagmulim_total
            else:
                tagmulim_aggregate_by_kind["unknown"] += tagmulim_total

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
            "הרכיבים הללו *חסומים לביצוע במערכת* (המרה/משיכה/טיפול תפעולי דורשים התחשבנות/השלמת רצפים מול הגוף המנהל). "
            "עם זאת, זה *לא* מונע מהסוכן לבצע ניתוח, השוואות וחישובים על שאר התיק: פשוט מתייחסים ליתרות החסומות כ'מחוץ לטווח הביצוע' "
            "ומחשבים על כל מה שניתן."
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

    context_lines.append("")
    context_lines.append("## לוגיקת משיכה/המרה לפי טורי טבלת המוצרים")
    context_lines.append(
        "החלוקה כאן היא לפי *העמודות/הרכיבים* (שהן הבסיס לכל פעולות ההמרה), עם סייגים לפי סוג מוצר כאשר החוק דורש זאת."
    )

    group_rows: list[tuple[str, float, dict[str, object]]] = []

    for field, amount in (
        ("פיצויים_מעסיק_נוכחי", float(conversion_totals["severance_current_employer"])),
        ("פיצויים_לאחר_התחשבנות", float(conversion_totals["severance_after_settlement"])),
        ("פיצויים_שלא_עברו_התחשבנות", float(conversion_totals["severance_not_settled"])),
        ("פיצויים_ממעסיקים_קודמים_רצף_זכויות", float(conversion_totals["severance_prev_employers_sequence_rights"])),
        ("פיצויים_ממעסיקים_קודמים_רצף_קצבה", float(conversion_totals["severance_prev_employers_sequence_pension"])),
    ):
        rule = _COMPONENT_RULES.get(field)
        if rule is None:
            continue
        group_rows.append((_FIELD_DISPLAY.get(field, field), amount, rule))

    tagmulim_to_2000 = float(
        conversion_totals["tagmulim_employee_to_2000"] + conversion_totals["tagmulim_employer_to_2000"]
    )
    if tagmulim_to_2000 > 0:
        base_rule = _COMPONENT_RULES.get("תגמולי_עובד_עד_2000") or {}
        group_rows.append(("תגמולי עד 2000 (עובד+מעביד)", tagmulim_to_2000, base_rule))

    tagmulim_after_2000 = float(
        conversion_totals["tagmulim_employee_after_2000"] + conversion_totals["tagmulim_employer_after_2000"]
    )
    if tagmulim_after_2000 > 0:
        base_rule = _COMPONENT_RULES.get("תגמולי_עובד_אחרי_2000") or {}
        group_rows.append(("תגמולי אחרי 2000 (עובד+מעביד)", tagmulim_after_2000, base_rule))

    tagmulim_after_2008_np = float(
        conversion_totals["tagmulim_employee_after_2008_non_paying"]
        + conversion_totals["tagmulim_employer_after_2008_non_paying"]
    )
    if tagmulim_after_2008_np > 0:
        base_rule = _COMPONENT_RULES.get("תגמולי_עובד_אחרי_2008_לא_משלמת") or {}
        group_rows.append(("תגמולי אחרי 2008 לא משלמת (עובד+מעביד)", tagmulim_after_2008_np, base_rule))

    if group_rows:
        for display, amount, rule in group_rows:
            context_lines.extend(_build_conversion_line(display=display, amount=amount, rule=rule))
    else:
        context_lines.append("לא נמצאו רכיבים חיוביים בטבלת המוצרים כדי להציג את חוקי ההמרה.")

    tagmulim_agg_total = float(sum(tagmulim_aggregate_by_kind.values()))
    if tagmulim_agg_total > 0:
        context_lines.append("")
        context_lines.append(
            "**תגמולים/סך תגמולים ללא פירוט רכיבים (בחשבונות שבהם אין עמודות מפורטות):**"
        )

        agg_rows = [
            ("קרן השתלמות", "education_fund"),
            ("גמל להשקעה", "investment_provident_fund"),
            ("קופת גמל", "regular_provident_fund"),
            ("קרן פנסיה/ביטוח מנהלים", "pension_or_insurance"),
            ("לא מזוהה", "unknown"),
        ]
        for display, key in agg_rows:
            amt = float(tagmulim_aggregate_by_kind.get(key) or 0)
            if amt <= 0:
                continue
            rule = _rule_for_tagmulim_by_product_type(product_type=display)
            context_lines.extend(
                _build_conversion_line(
                    display=f"תגמולים ללא פירוט ({display})",
                    amount=amt,
                    rule=rule,
                )
            )

    if education_fund_total_balance > 0 or investment_provident_total_balance > 0:
        context_lines.append("")
        context_lines.append("**סייגים לפי סוג מוצר (חוקי המרה מיוחדים):**")
        if education_fund_total_balance > 0:
            context_lines.append(
                f"- סה\"כ בקרנות השתלמות: {education_fund_total_balance:,.0f} ₪"
            )
            context_lines.append(
                "  בקרן השתלמות: המערכת מתייחסת לכספים כהוניים, ויחסי המס בהמרה הם פטור ממס (גם להון וגם לקצבה)."
            )
        if investment_provident_total_balance > 0:
            context_lines.append(
                f"- סה\"כ בגמל להשקעה: {investment_provident_total_balance:,.0f} ₪"
            )
            context_lines.append(
                "  בגמל להשקעה: הון -> מס רווח הון; קצבה -> פטור ממס (לפי חוקי ההמרה)."
            )

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
        context_lines.append(
            f"  • הון הוני בלבד (למשל קרן השתלמות/גמל להשקעה): {total_capital_only:,.0f} ₪"
        )
        capital_only_accounts = [p for p in products_list if p.get("is_capital_only")]
        capital_only_sorted = sorted(
            capital_only_accounts,
            key=lambda p: float(p.get("balance") or 0),
            reverse=True,
        )
        context_lines.append("    ◦ פירוט (כדי לשייך לטבלת המוצרים):")
        for p in capital_only_sorted[:10]:
            context_lines.append(f"      - {(p.get('name') or '')[:60]} | {float(p.get('balance') or 0):,.0f} ₪")
            if p.get("account_number"):
                context_lines.append(f"        מספר חשבון: {p.get('account_number')}")

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
    context_lines.append(
        "🔧 **אופציונלי (רק אם המשתמש ביקש יעד קצבה מספרי):** הפעל BUILD_TARGET_PENSION_PLAN עם יעד קצבה (למשל 20000)."
    )
    context_lines.append("   הכלי יחזיר מקדמים אמיתיים לפי גיל, מין וסוג מוצר.")

    return context_lines
