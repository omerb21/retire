import json
import logging
import re

logger = logging.getLogger("app.llm_chat.text_formatters")


def _parse_get_pension_products_payload(
    tool_result: str,
) -> tuple[str, list[dict], str]:
    raw = tool_result or ""
    if not isinstance(raw, str) or not raw.strip():
        return "", [], ""
    try:
        parsed_products = json.loads(raw)
    except Exception:
        return raw, [], ""

    products = None
    summary_text = ""
    if isinstance(parsed_products, dict):
        products = parsed_products.get("products")
        summary_text = str(parsed_products.get("summary") or "").strip()
    if not isinstance(products, list):
        if isinstance(parsed_products, dict) and isinstance(
            parsed_products.get("items"), list
        ):
            products = parsed_products.get("items")
        else:
            products = []

    normalized_products = [p for p in products if isinstance(p, dict)]
    return raw, normalized_products, summary_text


def _get_pension_products_amount(product: dict) -> float:
    try:
        amount = float(product.get("balance") or 0)
    except Exception:
        amount = 0.0
    if amount > 0:
        return amount
    try:
        return float(product.get("current_value") or 0)
    except Exception:
        return 0.0


def _append_get_pension_products_account_lines(
    lines: list[str], products: list[dict], *, include_header: bool = True
) -> None:
    lines.append("")
    if include_header:
        lines.append("חשבונות לדוגמה:")
    for idx, product in enumerate(products[:10], start=1):
        if not isinstance(product, dict):
            continue
        category = str(product.get("category") or "").strip() or "unknown"
        name = str(
            product.get("fund_name")
            or product.get("asset_name")
            or product.get("account")
            or "ללא שם"
        ).strip()
        amount = _get_pension_products_amount(product)
        lines.append(f"{idx}. {name} ({category}) – {amount:,.0f} ₪")


def _append_get_pension_products_summary_lines(
    lines: list[str], products: list[dict], summary_text: str
) -> None:
    total = sum(_get_pension_products_amount(product) for product in products)
    lines.append(f"מספר מוצרים: {len(products)}")
    lines.append(f'סה"כ יתרות: {total:,.0f} ₪')
    if summary_text:
        lines.append(f"מצב כללי: {summary_text}")


def format_get_pension_products_system_results(tool_result: str) -> str:
    raw, products, summary_text = _parse_get_pension_products_payload(tool_result)
    if not raw:
        return "(tool returned empty payload)"
    if not products and raw.lstrip()[:1] not in {"{", "["}:
        return raw

    lines: list[str] = ["תוצאות בפועל במערכת", "רשימת מוצרים"]
    if summary_text:
        lines.append(f"מצב כללי: {summary_text}")
    lines.append(f"מספר מוצרים: {len(products)}")
    lines.append(
        f'סה"כ יתרות: {sum(_get_pension_products_amount(product) for product in products):,.0f} ₪'
    )

    if not products:
        lines.append("לא נמצאו מוצרים במערכת ללקוח.")
        return "\n".join(lines).strip()

    _append_get_pension_products_account_lines(
        lines,
        products,
        include_header=False,
    )

    return "\n".join(lines).strip()


def format_get_pension_products_portfolio_analysis_short_default(
    tool_result: str,
) -> str:
    raw, products, summary_text = _parse_get_pension_products_payload(tool_result)
    if not raw:
        return "(tool returned empty payload)"
    if not products and raw.lstrip()[:1] not in {"{", "["}:
        return raw

    lines: list[str] = ["סיכום מהיר (הערכה ראשונית)"]
    if not products:
        if summary_text:
            lines.append(summary_text)
        lines.append("לא נמצאו מוצרים במערכת ללקוח.")
        lines.append("מה אפשר לעשות עכשיו: לבקש ניתוח או הרחבה של התיק.")
        lines.append("אם תרצה פירוט מלא כתוב: הרחב")
        return "\n".join(lines)

    _append_get_pension_products_summary_lines(lines, products, summary_text)
    _append_get_pension_products_account_lines(
        lines,
        products,
        include_header=True,
    )

    lines.append("")
    lines.append("מה אפשר לעשות עכשיו: לבקש ניתוח או הרחבה של התיק.")
    lines.append("אם תרצה פירוט מלא כתוב: הרחב")
    return "\n".join(lines).strip()


def format_tool_output_for_user_stream(tool_name: str, tool_result: str) -> str:
    if not isinstance(tool_name, str) or not tool_name:
        return tool_result

    if isinstance(tool_result, str) and tool_result.strip().lower().startswith(
        "error:"
    ):
        return tool_result

    if tool_name == "GET_SYSTEM_STATE_SNAPSHOT":
        raw = tool_result or ""
        if not isinstance(raw, str) or not raw.strip():
            try:
                logger.warning("GET_SYSTEM_STATE_SNAPSHOT returned empty payload")
            except Exception:
                pass
            return "(tool returned empty payload)"
        try:
            parsed_snapshot = json.loads(raw)
        except Exception:
            return raw
        if not isinstance(parsed_snapshot, dict) or not parsed_snapshot:
            try:
                logger.warning(
                    "GET_SYSTEM_STATE_SNAPSHOT returned non-dict/empty payload"
                )
            except Exception:
                pass
            return "(tool returned empty payload)"
        try:
            return json.dumps(
                parsed_snapshot, ensure_ascii=False, indent=2, sort_keys=True
            )
        except Exception:
            return raw

    if tool_name == "GET_PENSION_PRODUCTS":
        raw, products, summary_text = _parse_get_pension_products_payload(tool_result)
        if not raw:
            return "(tool returned empty payload)"
        if not products and raw.lstrip()[:1] not in {"{", "["}:
            return raw

        lines: list[str] = []
        lines.append("סיכום מהיר (הערכה ראשונית)")
        if not products:
            if summary_text:
                lines.append(summary_text)
            lines.append("לא נמצאו מוצרים במערכת ללקוח.")
            return "\n".join(lines)

        _append_get_pension_products_summary_lines(lines, products, summary_text)
        _append_get_pension_products_account_lines(
            lines,
            products,
            include_header=True,
        )

        return "\n".join(lines).strip()

    if tool_name == "BUILD_TARGET_PENSION_PLAN":
        raw = tool_result or ""
        try:
            parsed = json.loads(raw)
        except Exception:
            return tool_result
        if not isinstance(parsed, dict):
            return tool_result

        plan_data = (
            parsed.get("result") if isinstance(parsed.get("result"), dict) else parsed
        )
        if not isinstance(plan_data, dict):
            return tool_result

        offsets = (
            parsed.get("offsets") if isinstance(parsed.get("offsets"), dict) else {}
        )
        retirement_age = plan_data.get("retirement_age")
        if retirement_age is None:
            retirement_age = parsed.get("retirement_age")
        target_is_net = plan_data.get("target_is_net")
        if target_is_net is None:
            target_is_net = parsed.get("target_is_net")
        target_monthly = plan_data.get("target_monthly_pension")
        if target_monthly is None:
            target_monthly = parsed.get("target_monthly_pension")

        mode_label = "נטו" if bool(target_is_net) else "ברוטו"
        lines: list[str] = []
        lines.append("תכנית יעד קצבה – סיכום:")
        if retirement_age is not None:
            try:
                lines.append(f"- גיל פרישה בתכנון: {int(retirement_age)}")
            except Exception:
                lines.append(f"- גיל פרישה בתכנון: {retirement_age}")
        lines.append("- תכנון בלבד")
        lines.append("- לא בוצעה עזיבת עבודה")
        lines.append("- לא אבצע עזיבת עבודה")
        if target_monthly is not None:
            try:
                lines.append(
                    f"- יעד קצבה חודשי ({mode_label}): {float(target_monthly):,.0f} ₪"
                )
            except Exception:
                lines.append(f"- יעד קצבה חודשי ({mode_label}): {target_monthly} ₪")
        desired_net_total = offsets.get("desired_net_total")
        if bool(target_is_net) and desired_net_total is None:
            desired_net_total = target_monthly
        if bool(target_is_net) and desired_net_total is not None:
            try:
                lines.append(f"- יעד נטו: {float(desired_net_total):,.0f} ₪")
            except Exception:
                lines.append(f"- יעד נטו: {desired_net_total} ₪")
        lines.append("- אם תרצה לבצע עזיבת עבודה נבקש אישור מפורש")
        return "\n".join(lines)

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
                lines.append(
                    f"• חיסכון מס בפריסה (השוואה): {float(tax_benefit):,.0f} ₪"
                )
            return "\n".join(lines)

        if tool_name == "CALCULATE_TAX_EXEMPT_PENSION" and isinstance(parsed, dict):
            result = (
                parsed.get("result")
                if isinstance(parsed.get("result"), dict)
                else parsed
            )
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
                lines.append(
                    f"• קצבה פטורה לפני קיזוז: {float(initial_exempt):,.0f} ₪/חודש"
                )
            if final_exempt is not None:
                lines.append(
                    f"• קצבה פטורה אחרי קיזוז: {float(final_exempt):,.0f} ₪/חודש"
                )
            if monthly_loss is not None:
                lines.append(
                    f"• ירידה חודשית בקצבה הפטורה: {float(monthly_loss):,.0f} ₪/חודש"
                )
            return "\n".join(lines)

        if tool_name == "PROCESS_TERMINATION" and isinstance(parsed, dict):
            success = parsed.get("success")
            if (
                success is None
                and str(parsed.get("status") or "").strip().lower() == "done"
            ):
                success = True
            message = parsed.get("message")
            details = (
                parsed.get("details") if isinstance(parsed.get("details"), dict) else {}
            )
            choices = (
                parsed.get("choices") if isinstance(parsed.get("choices"), dict) else {}
            )
            already_processed = bool(details.get("already_processed")) or (
                isinstance(message, str)
                and ("כבר בוצע" in message or "כבר בוצעה" in message)
            )
            termination_date = details.get("termination_date")
            severance_amount = details.get("severance_amount")
            exempt_amount = details.get("exempt_amount")
            taxable_amount = details.get("taxable_amount")
            exempt_choice = details.get("exempt_choice") or choices.get("exempt")
            taxable_choice = details.get("taxable_choice") or choices.get("taxable")
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
                    lines.append(
                        f'• סה"כ פיצויים שטופלו: {float(severance_amount):,.0f} ₪'
                    )
                except Exception:
                    lines.append(f'• סה"כ פיצויים שטופלו: {severance_amount} ₪')
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
                    lines.append(
                        f"• סכום היוון: {float(parsed.get('commutation_amount')):,.0f} ₪"
                    )
                except Exception:
                    lines.append(f"• סכום היוון: {parsed.get('commutation_amount')} ₪")
            if parsed.get("commutation_date"):
                lines.append(f"• תאריך: {parsed.get('commutation_date')}")
            if parsed.get("tax_treatment"):
                lines.append(f"• יחס מס: {parsed.get('tax_treatment')}")
            if parsed.get("new_balance") is not None:
                try:
                    lines.append(
                        f"• יתרה חדשה בקצבה: {float(parsed.get('new_balance')):,.0f} ₪"
                    )
                except Exception:
                    lines.append(f"• יתרה חדשה בקצבה: {parsed.get('new_balance')} ₪")
            if parsed.get("new_pension_amount") is not None:
                try:
                    lines.append(
                        f"• קצבה חודשית חדשה: {float(parsed.get('new_pension_amount')):,.0f} ₪"
                    )
                except Exception:
                    lines.append(
                        f"• קצבה חודשית חדשה: {parsed.get('new_pension_amount')} ₪"
                    )
            return "\n".join(lines)

        if (
            tool_name == "GENERATE_FULL_REPORT"
            or tool_name == "GENERATE_TAX_DEDUCTION_DOCUMENTS"
        ):
            try:
                parsed_doc = json.loads(tool_result)
            except Exception:
                return tool_result
            if not isinstance(parsed_doc, dict):
                return tool_result

            status_message = parsed_doc.get("status_message") or parsed_doc.get(
                "message"
            )
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
                    lines.append(
                        f"• קצבה פטורה חודשית: {float(parsed_fix.get('monthly_exempt_pension')):,.2f} ₪"
                    )
                except Exception:
                    lines.append(
                        f"• קצבה פטורה חודשית: {parsed_fix.get('monthly_exempt_pension')} ₪"
                    )
            if parsed_fix.get("exempt_pension_percentage") is not None:
                try:
                    lines.append(
                        f"• אחוז קצבה פטורה: {float(parsed_fix.get('exempt_pension_percentage'))*100:.2f}%"
                    )
                except Exception:
                    lines.append(
                        f"• אחוז קצבה פטורה: {parsed_fix.get('exempt_pension_percentage')}"
                    )
            if parsed_fix.get("exempt_capital_initial") is not None:
                try:
                    lines.append(
                        f"• הון פטור ראשוני: {float(parsed_fix.get('exempt_capital_initial')):,.2f} ₪"
                    )
                except Exception:
                    lines.append(
                        f"• הון פטור ראשוני: {parsed_fix.get('exempt_capital_initial')} ₪"
                    )
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
                    lines.append(
                        f"• נטו מאושר לתיעוד: {float(parsed_submit.get('final_net_amount')):,.0f} ₪"
                    )
                except Exception:
                    lines.append(
                        f"• נטו מאושר לתיעוד: {parsed_submit.get('final_net_amount')} ₪"
                    )
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
                lines.append(
                    f"• מזהה נכס היוון: {parsed_exec.get('commutation_asset_id')}"
                )
            if parsed_exec.get("commutation_amount") is not None:
                try:
                    lines.append(
                        f"• סכום היוון: {float(parsed_exec.get('commutation_amount')):,.0f} ₪"
                    )
                except Exception:
                    lines.append(
                        f"• סכום היוון: {parsed_exec.get('commutation_amount')} ₪"
                    )
            if parsed_exec.get("commutation_date"):
                lines.append(f"• תאריך: {parsed_exec.get('commutation_date')}")
            if parsed_exec.get("tax_treatment"):
                lines.append(f"• יחס מס: {parsed_exec.get('tax_treatment')}")
            if parsed_exec.get("new_balance") is not None:
                try:
                    lines.append(
                        f"• יתרה חדשה בקצבה: {float(parsed_exec.get('new_balance')):,.0f} ₪"
                    )
                except Exception:
                    lines.append(
                        f"• יתרה חדשה בקצבה: {parsed_exec.get('new_balance')} ₪"
                    )
            if parsed_exec.get("new_pension_amount") is not None:
                try:
                    lines.append(
                        f"• קצבה חודשית חדשה: {float(parsed_exec.get('new_pension_amount')):,.0f} ₪"
                    )
                except Exception:
                    lines.append(
                        f"• קצבה חודשית חדשה: {parsed_exec.get('new_pension_amount')} ₪"
                    )
            return "\n".join(lines)

    if tool_name != "RUN_RETIREMENT_CASHFLOW_ANALYSIS":
        return tool_result

    try:
        parsed = json.loads(tool_result)
    except Exception:
        return tool_result

    # Support both payload shapes:
    # 1) legacy: flat dict with computed fields
    # 2) full tool payload: {success, tool_name, result: {...}, explanation: "..."}
    if isinstance(parsed, dict):
        explanation = parsed.get("explanation")
        if isinstance(explanation, str) and explanation.strip():
            return explanation.strip()
        data = (
            parsed.get("result") if isinstance(parsed.get("result"), dict) else parsed
        )
    else:
        data = parsed

    if not isinstance(data, dict):
        return tool_result

    gross_total = (
        data.get("total_guaranteed_income")
        or data.get("total_guaranteed_income_gross")
        or data.get("projected_pension")
    )
    net_total = data.get("total_guaranteed_income_net") or data.get(
        "projected_pension_net"
    )
    monthly_net_pension = data.get("projected_pension_net")
    additional_gross = data.get("additional_income_gross_monthly")
    additional_taxable_gross = data.get("additional_income_taxable_gross_monthly")
    additional_exempt_gross = data.get("additional_income_exempt_gross_monthly")
    income_tax = data.get("monthly_income_tax")
    total_tax = data.get("monthly_tax_deduction")
    exempt_pct = data.get("exemption_percentage")
    exempt_amount = data.get("exempt_pension_monthly")
    liquid_capital = data.get("total_liquid_capital")
    suff_years = data.get("capital_sufficiency_years")
    is_sustainable = data.get("is_sustainable")

    lines: list[str] = []
    lines.append("ניתוח פרישה – עיקרי התוצאות (חודשיות):")
    if gross_total is not None:
        lines.append(f'• סה"כ הכנסה ברוטו: {gross_total:,.0f} ₪')
    if income_tax is not None or total_tax is not None:
        tax_to_show = income_tax if income_tax is not None else total_tax
        if tax_to_show is not None:
            lines.append(f'• מס הכנסה חודשי (סה"כ הכנסות חייבות): {tax_to_show:,.0f} ₪')
    if net_total is not None:
        lines.append(f'• סה"כ הכנסה נטו: {net_total:,.0f} ₪')
    if monthly_net_pension is not None:
        lines.append(f'• פנסיה נטו (מתוך הסה"כ): {monthly_net_pension:,.0f} ₪')
    if (
        additional_gross is not None
        or additional_taxable_gross is not None
        or additional_exempt_gross is not None
    ):
        parts: list[str] = []
        if additional_gross is not None:
            parts.append(f'סה"כ הכנסות נוספות (ברוטו): {additional_gross:,.0f} ₪')
        if additional_taxable_gross is not None:
            parts.append(f"חייבות במס: {additional_taxable_gross:,.0f} ₪")
        if additional_exempt_gross is not None:
            parts.append(f"פטורות: {additional_exempt_gross:,.0f} ₪")
        if parts:
            lines.append("• הכנסות נוספות: " + " | ".join(parts))

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
    else:
        lines.append("• קיימות כספית: אין גירעון חודשי")
    if is_sustainable is not None:
        lines.append(f"• בר-קיימא: {'כן' if bool(is_sustainable) else 'לא'}")

    return "\n".join(lines)


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

    try:
        updated = re.sub(r"conversation transcript", "", updated, flags=re.IGNORECASE)
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
    updated = re.sub(
        r"^\s*[A-Z0-9_]+_HANDLER_VERSION=.*$", "", updated, flags=re.MULTILINE
    )
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
