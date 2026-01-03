from typing import Any

from app.services.pension_portfolio.conversion_rules import (
    COMPONENT_RULES,
    rule_for_tagmulim_by_product_type,
)


def _clean_account_name_for_transform(source_name: str | None) -> str:
    raw = (source_name or "").strip()
    if not raw:
        return raw
    if "(" in raw:
        prefix = raw.split("(", 1)[0].strip()
        return prefix or raw
    return raw


def build_transform_accounts_from_target_plan_payload(payload: dict) -> list[dict]:
    result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
    sources_used = result.get("sources_used") if isinstance(result.get("sources_used"), list) else []

    required_gross = result.get("required_gross_for_target")
    if required_gross is None:
        required_gross = result.get("target_monthly_pension")
    try:
        required_gross_val = float(required_gross or 0)
    except Exception:
        required_gross_val = 0.0

    def _is_pension_only_component(*, field: str, product_type: str) -> bool:
        if not field:
            return False
        if field == "תגמולים":
            rule = rule_for_tagmulim_by_product_type(product_type=product_type)
            try:
                can_pension = bool(rule.get("pension"))
            except Exception:
                can_pension = True
            try:
                can_capital = bool(rule.get("capital") or rule.get("capital_asset"))
            except Exception:
                can_capital = False
            return can_pension and (not can_capital)

        rule = COMPONENT_RULES.get(field)
        if not isinstance(rule, dict):
            return False
        try:
            can_pension = bool(rule.get("pension"))
        except Exception:
            can_pension = True
        try:
            can_capital = bool(rule.get("capital") or rule.get("capital_asset"))
        except Exception:
            can_capital = False
        return can_pension and (not can_capital)

    normalized_sources: list[dict[str, Any]] = []
    for src in sources_used:
        if not isinstance(src, dict):
            continue
        if src.get("source_type") != "pension_fund_from_portfolio":
            continue
        account_number = str(src.get("account_number") or "").strip()
        field = str(src.get("component_field") or "").strip()
        if not account_number or not field:
            continue

        try:
            balance_used = float(src.get("balance_used") or 0)
        except Exception:
            balance_used = 0.0
        if balance_used <= 0:
            continue

        try:
            annuity_factor = float(src.get("annuity_factor") or 0)
        except Exception:
            annuity_factor = 0.0
        if annuity_factor <= 0:
            continue

        try:
            pension_used = float(src.get("pension_used") or 0)
        except Exception:
            pension_used = 0.0
        if pension_used <= 0:
            pension_used = float(balance_used) / float(annuity_factor)

        product_type = str(src.get("fund_type") or "")
        normalized_sources.append(
            {
                "src": src,
                "account_number": account_number,
                "field": field,
                "balance_used": balance_used,
                "annuity_factor": annuity_factor,
                "pension_used": pension_used,
                "product_type": product_type,
                "is_pension_only": _is_pension_only_component(
                    field=field, product_type=product_type
                ),
            }
        )

    if not normalized_sources:
        return []

    selected: list[dict[str, Any]] = []
    accumulated = 0.0

    def _maybe_add_source(item: dict[str, Any]) -> None:
        nonlocal accumulated
        if required_gross_val > 0 and accumulated >= required_gross_val:
            return

        needed = (required_gross_val - accumulated) if required_gross_val > 0 else None
        if needed is None or needed <= 0:
            selected.append(item)
            accumulated += float(item.get("pension_used") or 0)
            return

        pension_used = float(item.get("pension_used") or 0)
        if pension_used <= needed:
            selected.append(item)
            accumulated += pension_used
            return

        # Partial conversion on the last component to reach the target.
        annuity_factor = float(item.get("annuity_factor") or 0)
        if annuity_factor <= 0:
            return
        partial_balance = float(needed) * annuity_factor
        if partial_balance <= 0:
            return
        if partial_balance > float(item.get("balance_used") or 0):
            partial_balance = float(item.get("balance_used") or 0)
        if partial_balance <= 0:
            return

        trimmed = dict(item)
        trimmed["balance_used"] = partial_balance
        trimmed["pension_used"] = float(partial_balance) / annuity_factor
        selected.append(trimmed)
        accumulated += float(trimmed.get("pension_used") or 0)

    # Step 1: pension-only components first (preserve original order)
    for item in normalized_sources:
        if bool(item.get("is_pension_only")):
            _maybe_add_source(item)

    # Step 2: only if needed, add capital-eligible components in plan order
    for item in normalized_sources:
        if required_gross_val > 0 and accumulated >= required_gross_val:
            break
        if bool(item.get("is_pension_only")):
            continue
        _maybe_add_source(item)

    accounts_map: dict[str, dict] = {}
    for item in selected:
        src = item.get("src") if isinstance(item.get("src"), dict) else {}
        account_number = str(item.get("account_number") or "").strip()
        field = str(item.get("field") or "").strip()
        try:
            amount = float(item.get("balance_used") or 0)
        except Exception:
            amount = 0.0
        if not account_number or not field or amount <= 0:
            continue

        start_date_raw = src.get("start_date")
        row = accounts_map.get(account_number)
        if row is None:
            acc_name = None
            try:
                acc_name = str(src.get("plan_name") or "").strip() or None
            except Exception:
                acc_name = None
            if acc_name is None:
                acc_name = _clean_account_name_for_transform(
                    str(src.get("source_name") or "")
                )
            row = {
                "account_name": acc_name,
                "product_type": str(src.get("fund_type") or ""),
                "company": str(src.get("company") or ""),
                "account_number": account_number,
                "start_date": start_date_raw,
                "specific_amounts": {},
                "component_conversion_overrides": {},
            }
            accounts_map[account_number] = row
        else:
            if (not row.get("start_date")) and start_date_raw:
                row["start_date"] = start_date_raw

        specific = row.get("specific_amounts")
        if not isinstance(specific, dict):
            specific = {}
            row["specific_amounts"] = specific
        specific[field] = float(specific.get(field, 0) or 0) + float(amount)

        overrides = row.get("component_conversion_overrides")
        if not isinstance(overrides, dict):
            overrides = {}
            row["component_conversion_overrides"] = overrides
        overrides[field] = "pension"

    return list(accounts_map.values())
