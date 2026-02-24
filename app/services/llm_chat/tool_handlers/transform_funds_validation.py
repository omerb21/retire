from __future__ import annotations

from app.services.pension_portfolio.conversion_rules import (
    preferred_conversion_type_for_component,
    validate_component_conversion,
)

from .transform_funds_classification import classify_product_type
from .transform_funds_conversion import (
    _build_specific_amounts_from_account,
    _is_allowed_capital_without_breakdown,
    _normalize_specific_amounts,
)


def build_conversion_tasks_from_accounts(
    *,
    accounts: list,
    blocked_fields: set[str],
    ignore_blocked_balances: bool,
    skip_non_convertible_accounts: bool,
    commute_pension_components: bool,
    default_conversion_type: str,
    skipped_accounts: int,
    blocked_field_amount: float,
) -> tuple[list[dict], list[str], list[dict[str, str]], list[dict], int, float]:
    conversion_tasks: list[dict] = []
    validation_errors: list[str] = []
    skipped_non_convertible: list[dict[str, str]] = []
    skipped_items: list[dict] = []

    for idx, account in enumerate(accounts):
        if not isinstance(account, dict):
            validation_errors.append(f"חשבון {idx + 1}: פורמט חשבון לא תקין")
            continue

        account_name = account.get("account_name") or account.get(
            "שם_תכנית", f"חשבון {idx + 1}"
        )
        product_type = account.get("product_type") or account.get("סוג_מוצר", "")
        rules_product_type = f"{product_type or ''} {account_name or ''}".strip()
        account_number = (
            account.get("account_number")
            or account.get("מספר_חשבון")
            or account.get("מספר חשבון")
            or account.get("מספר-חשבון")
            or ""
        )
        if not str(account_number).strip():
            msg = f"{account_name}: חסר מספר חשבון (מספר_חשבון) ולכן לא ניתן לבצע המרה בטוחה"
            if skip_non_convertible_accounts:
                skipped_items.append(
                    {
                        "account_name": account_name,
                        "account_number": "",
                        "field": "מספר_חשבון",
                        "amount": 0,
                        "reason": msg,
                    }
                )
                skipped_accounts += 1
                continue
            validation_errors.append(msg)
            continue

        specific_amounts = account.get("specific_amounts")
        if isinstance(specific_amounts, dict) and specific_amounts:
            specific_amounts = _normalize_specific_amounts(specific_amounts)
        else:
            specific_amounts = _build_specific_amounts_from_account(account)

        if ignore_blocked_balances and specific_amounts:
            for bf in blocked_fields:
                raw_val = specific_amounts.get(bf)
                try:
                    val = float(raw_val or 0)
                except (TypeError, ValueError):
                    val = 0.0
                if val > 0:
                    blocked_field_amount += val
                    specific_amounts.pop(bf, None)

        raw_employer_current = specific_amounts.get(
            "פיצויים_מעסיק_נוכחי", account.get("פיצויים_מעסיק_נוכחי")
        )
        try:
            employer_current_val = float(raw_employer_current or 0)
        except (TypeError, ValueError):
            employer_current_val = 0.0
        if employer_current_val > 0:
            msg = (
                "לא ניתן להמיר רכיב 'פיצויים מעסיק נוכחי' מתוך טבלת המוצרים. "
                "יש לבצע עזיבת עבודה (מעסיק נוכחי) במסך מעסיק נוכחי."
            )
            skipped_items.append(
                {
                    "account_name": account_name,
                    "account_number": str(account_number).strip(),
                    "field": "פיצויים_מעסיק_נוכחי",
                    "amount": employer_current_val,
                    "reason": msg,
                }
            )
            specific_amounts.pop("פיצויים_מעסיק_נוכחי", None)

            raw_total_contrib = account.get("סך_תגמולים")
            try:
                total_contrib_val = float(raw_total_contrib or 0)
            except (TypeError, ValueError):
                total_contrib_val = 0.0
            raw_tagmulim = specific_amounts.get("תגמולים")
            try:
                tagmulim_val = float(raw_tagmulim or 0)
            except (TypeError, ValueError):
                tagmulim_val = 0.0
            if (
                tagmulim_val > 0
                and total_contrib_val <= 0
                and abs(tagmulim_val - employer_current_val)
                <= max(1.0, employer_current_val * 0.001)
            ):
                specific_amounts.pop("תגמולים", None)

        if not specific_amounts and (
            (
                isinstance(account.get("specific_amounts"), dict)
                and bool(account.get("specific_amounts"))
            )
            or any(
                k in account
                for k in (
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
                )
            )
        ):
            skipped_accounts += 1
            continue

        if specific_amounts:
            pension_components: dict[str, float] = {}
            capital_components_by_tax: dict[str, dict[str, float]] = {}
            commutation_components: dict[str, float] = {}

            component_overrides = account.get("component_conversion_overrides")
            if not isinstance(component_overrides, dict):
                component_overrides = {}

            for field, val in list(specific_amounts.items()):
                try:
                    numeric_val = float(val or 0)
                except (TypeError, ValueError):
                    numeric_val = 0.0
                if numeric_val <= 0:
                    continue

                override_raw = component_overrides.get(field)
                override = (
                    str(override_raw).strip().lower()
                    if override_raw is not None
                    else ""
                )
                if override in {"pension", "capital_asset"}:
                    preferred = override
                else:
                    preferred = preferred_conversion_type_for_component(
                        field=field,
                        product_type=rules_product_type,
                    )
                ok, _tax, err_msg = validate_component_conversion(
                    field=field,
                    amount=numeric_val,
                    conversion_type=preferred,
                    product_type=rules_product_type,
                )
                chosen = preferred
                chosen_tax = _tax
                if not ok:
                    alt = "capital_asset" if preferred == "pension" else "pension"
                    ok2, _tax2, err_msg2 = validate_component_conversion(
                        field=field,
                        amount=numeric_val,
                        conversion_type=alt,
                        product_type=rules_product_type,
                    )
                    if ok2:
                        chosen = alt
                        chosen_tax = _tax2
                    else:
                        msg = err_msg2 or err_msg or f"לא ניתן להמיר רכיב {field}"
                        if skip_non_convertible_accounts:
                            skipped_non_convertible.append(
                                {
                                    "account_name": account_name,
                                    "reason": f"{msg} ({field})",
                                }
                            )
                            skipped_items.append(
                                {
                                    "account_name": account_name,
                                    "account_number": str(account_number).strip(),
                                    "field": field,
                                    "amount": numeric_val,
                                    "reason": msg,
                                }
                            )
                            continue
                        validation_errors.append(f"{account_name}: {msg} ({field})")
                        continue

                if chosen == "pension":
                    if commute_pension_components:
                        commutation_components[field] = float(
                            commutation_components.get(field, 0) + numeric_val
                        )
                    else:
                        pension_components[field] = float(
                            pension_components.get(field, 0) + numeric_val
                        )
                else:
                    tax_key = str(chosen_tax or "taxable")
                    bucket = capital_components_by_tax.get(tax_key)
                    if bucket is None:
                        bucket = {}
                        capital_components_by_tax[tax_key] = bucket
                    bucket[field] = float(bucket.get(field, 0) + numeric_val)

            pension_sum = sum(pension_components.values())
            capital_sum = sum(
                sum(parts.values()) for parts in capital_components_by_tax.values()
            )
            commutation_sum = sum(commutation_components.values())

            if pension_sum <= 0 and capital_sum <= 0 and commutation_sum <= 0:
                skipped_accounts += 1
                continue

            if pension_sum > 0:
                conversion_tasks.append(
                    {
                        "task_type": "pension",
                        "account": account,
                        "account_name": account_name,
                        "product_type": product_type,
                        "company": account.get("company")
                        or account.get("חברה_מנהלת", ""),
                        "account_number": str(account_number).strip(),
                        "amount": pension_sum,
                        "components": pension_components,
                    }
                )

            if commutation_sum > 0:
                conversion_tasks.append(
                    {
                        "task_type": "commutation",
                        "account": account,
                        "account_name": account_name,
                        "product_type": product_type,
                        "company": account.get("company")
                        or account.get("חברה_מנהלת", ""),
                        "account_number": str(account_number).strip(),
                        "amount": commutation_sum,
                        "components": commutation_components,
                        "tax_treatment": "taxable",
                    }
                )

            if capital_sum > 0:
                for tax_treatment, parts in capital_components_by_tax.items():
                    part_sum = sum(float(v or 0) for v in (parts or {}).values())
                    if part_sum <= 0:
                        continue
                    conversion_tasks.append(
                        {
                            "task_type": "capital_asset",
                            "account": account,
                            "account_name": account_name,
                            "product_type": product_type,
                            "company": account.get("company")
                            or account.get("חברה_מנהלת", ""),
                            "account_number": str(account_number).strip(),
                            "amount": part_sum,
                            "components": parts,
                            "tax_treatment": str(tax_treatment),
                        }
                    )
            continue

        conversion_type = account.get("conversion_type")
        if not conversion_type:
            conversion_type = classify_product_type(
                product_type_str=f"{product_type or ''} {account_name or ''}",
                default_conversion_type=default_conversion_type,
            )

        try:
            balance_val = float(account.get("balance") or account.get("יתרה") or 0)
        except (TypeError, ValueError):
            balance_val = 0.0

        if balance_val <= 0:
            skipped_accounts += 1
            continue

        if conversion_type == "pension":
            msg = f"{account_name}: אין פירוט רכיבים ולכן אסור להמיר מוצר קצבתי (ולהפריד פיצויים חסומים/הוניים) באופן בטוח"
            if skip_non_convertible_accounts:
                skipped_non_convertible.append(
                    {"account_name": account_name, "reason": msg}
                )
                skipped_items.append(
                    {
                        "account_name": account_name,
                        "account_number": str(account_number).strip(),
                        "field": "יתרה",
                        "amount": balance_val,
                        "reason": msg,
                    }
                )
                continue
            validation_errors.append(msg)
            continue

        if conversion_type == "capital_asset":
            if not _is_allowed_capital_without_breakdown(
                product_type=product_type,
                account_name=account_name,
            ):
                msg = f"{account_name}: אין פירוט רכיבים ולכן אסור להמיר להון עבור סוג מוצר זה ({product_type})"
                if skip_non_convertible_accounts:
                    skipped_non_convertible.append(
                        {"account_name": account_name, "reason": msg}
                    )
                    skipped_items.append(
                        {
                            "account_name": account_name,
                            "account_number": str(account_number).strip(),
                            "field": "יתרה",
                            "amount": balance_val,
                            "reason": msg,
                        }
                    )
                    continue
                validation_errors.append(msg)
                continue

            conversion_tasks.append(
                {
                    "task_type": "capital_asset",
                    "account": account,
                    "account_name": account_name,
                    "product_type": product_type,
                    "company": account.get("company") or account.get("חברה_מנהלת", ""),
                    "account_number": str(account_number).strip(),
                    "amount": balance_val,
                    "components": None,
                }
            )

    return (
        conversion_tasks,
        validation_errors,
        skipped_non_convertible,
        skipped_items,
        skipped_accounts,
        blocked_field_amount,
    )
