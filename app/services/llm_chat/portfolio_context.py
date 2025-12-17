from ...schemas.llm_chat import PensionPortfolioAccount


def build_pension_portfolio_context(portfolio: list[PensionPortfolioAccount]) -> list[str]:
    if not portfolio:
        return []

    context_lines: list[str] = []
    context_lines.append("")
    context_lines.append("📂 **תיק פנסיוני (נתונים גולמיים מקובץ מסלקה)**")
    context_lines.append("⚠️ **חובה:** להפעיל BUILD_TARGET_PENSION_PLAN לקבלת קצבה מחושבת עם מקדמים אמיתיים!")
    context_lines.append("")

    total_balance = 0.0
    total_severance = 0.0
    total_tagmulim = 0.0
    products_list: list[dict] = []
    canonical_accounts: list[dict] = []

    for acc in portfolio:
        balance = float(acc.יתרה or 0)
        if balance <= 0:
            continue

        total_balance += balance

        severance_current = float(acc.פיצויים_מעסיק_נוכחי or 0)
        severance_past = float(acc.פיצויים_ממעסיקים_קודמים_רצף_קצבה or 0)
        total_severance += severance_current + severance_past

        tagmulim = float(acc.תגמולים or acc.סך_תגמולים or 0)
        total_tagmulim += tagmulim

        product_type = acc.סוג_מוצר or "לא ידוע"
        product_lower = product_type.lower()

        account_number = (acc.מספר_חשבון or "").strip() or None
        start_date = (acc.תאריך_התחלה or "").strip() or None

        is_capital_only = False
        if "השתלמות" in product_lower:
            is_capital_only = True
            category = "הון בלבד"
        elif "גמל להשקעה" in product_lower:
            is_capital_only = True
            category = "הון (ניתן להמרה)"
        elif "קרן פנסיה" in product_lower or "פנסיה" in product_lower:
            category = "קצבתי"
        elif "ביטוח מנהלים" in product_lower or "ביטוח" in product_lower:
            category = "קצבתי"
        elif "קופת גמל" in product_lower:
            category = "קצבתי/הוני"
        elif "חיסכון" in product_lower:
            category = "הוני"
        else:
            category = "לחישוב"

        products_list.append(
            {
                "name": acc.שם_תכנית or "ללא שם",
                "company": acc.חברה_מנהלת or "",
                "type": product_type,
                "category": category,
                "balance": balance,
                "account_number": account_number,
                "start_date": start_date,
                "severance": severance_current + severance_past,
                "tagmulim": tagmulim,
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

    context_lines.append("| מוצר | סוג | סיווג | יתרה (₪) | מספר חשבון | תאריך התחלה |")
    context_lines.append("|------|------|-------|----------|------------|-------------|")

    for p in products_list:
        context_lines.append(
            f"| {p['name'][:30]} | {p['type'][:20]} | {p['category']} | {p['balance']:,.0f} | {p.get('account_number') or ''} | {p.get('start_date') or ''} |"
        )

    context_lines.append("")
    context_lines.append("**סיכום נתונים גולמיים:**")
    context_lines.append(f"  • סה\"כ יתרות: {total_balance:,.0f} ₪")
    if total_severance > 0:
        context_lines.append(f"  • מתוכם פיצויים: {total_severance:,.0f} ₪")
    if total_tagmulim > 0:
        context_lines.append(f"  • מתוכם תגמולים: {total_tagmulim:,.0f} ₪")

    total_capital_only = sum(p["balance"] for p in products_list if p["is_capital_only"])
    if total_capital_only > 0:
        context_lines.append(f"  • הון שלא ניתן להמרה: {total_capital_only:,.0f} ₪")

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
