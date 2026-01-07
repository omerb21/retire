from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from app.services.retirement_age_service import calculate_retirement_age

from .transform_funds_conversion import (
    _build_specific_amounts_from_account,
    _normalize_specific_amounts,
    _parse_date_value,
)

logger = logging.getLogger("app.llm_chat.tools")


def prepare_transform_funds_context(
    *,
    client_id,
    agent_tools,
    accounts,
    pension_start_date_raw,
    ignore_blocked_balances: bool,
    _DEFAULT_RETIREMENT_AGE_FALLBACK: int,
) -> dict:
    from datetime import date

    from datetime import date as date_type

    client_obj = getattr(agent_tools, "client", None)
    try:
        from app.services.retirement_age_service import DEFAULT_MALE_RETIREMENT_AGE

        retirement_age = int(DEFAULT_MALE_RETIREMENT_AGE)
    except Exception:
        retirement_age = int(_DEFAULT_RETIREMENT_AGE_FALLBACK)
    retirement_date: Optional[date] = None
    retirement_year = datetime.now().year
    if client_obj and getattr(client_obj, "birth_date", None) and getattr(client_obj, "gender", None):
        try:
            retirement_info = calculate_retirement_age(client_obj.birth_date, client_obj.gender)
            retirement_date = retirement_info.get("retirement_date")
            age_years = int(retirement_info.get("age_years") or retirement_age)
            age_months = int(retirement_info.get("age_months") or 0)
            retirement_age = age_years + (1 if age_months > 0 else 0)
            if retirement_date:
                retirement_year = retirement_date.year
        except Exception as e:
            logger.warning(
                "⚠️ Failed to calculate retirement age/date for client %s: %s",
                client_id,
                e,
            )

    try:
        current_age = None
        if client_obj and hasattr(client_obj, "get_age"):
            current_age = client_obj.get_age()
        if current_age is not None and int(current_age) >= int(retirement_age):
            retirement_age = int(current_age)
            retirement_date = date_type.today()
            retirement_year = retirement_date.year
    except Exception:
        pass

    global_pension_start_date = _parse_date_value(pension_start_date_raw)

    unresolved_severance_total = 0.0
    rights_sequence_total = 0.0
    blocked_field_amount = 0.0
    blocked_fields = {
        "פיצויים_שלא_עברו_התחשבנות",
        "פיצויים_ממעסיקים_קודמים_רצף_זכויות",
    }
    employer_current_severance_total = 0.0
    for account in accounts:
        if not isinstance(account, dict):
            continue
        specific_amounts = account.get("specific_amounts")
        if isinstance(specific_amounts, dict) and specific_amounts:
            specific_amounts = _normalize_specific_amounts(specific_amounts)
        else:
            specific_amounts = _build_specific_amounts_from_account(account)

        raw_emp_current = specific_amounts.get("פיצויים_מעסיק_נוכחי", account.get("פיצויים_מעסיק_נוכחי"))
        try:
            emp_current_val = float(raw_emp_current or 0)
        except (TypeError, ValueError):
            emp_current_val = 0.0
        if emp_current_val > 0:
            employer_current_severance_total += emp_current_val

        if ignore_blocked_balances and specific_amounts:
            for bf in blocked_fields:
                raw_val = specific_amounts.get(bf)
                try:
                    val = float(raw_val or 0)
                except (TypeError, ValueError):
                    val = 0.0
                if val > 0:
                    specific_amounts.pop(bf, None)

        for key, target in (
            ("פיצויים_שלא_עברו_התחשבנות", "unresolved"),
            ("פיצויים_ממעסיקים_קודמים_רצף_זכויות", "rights"),
        ):
            raw_val = specific_amounts.get(key, account.get(key))
            try:
                val = float(raw_val or 0)
            except (TypeError, ValueError):
                val = 0.0
            if target == "unresolved":
                unresolved_severance_total += val
            else:
                rights_sequence_total += val

    if (unresolved_severance_total > 0 or rights_sequence_total > 0) and (not ignore_blocked_balances):
        ignore_blocked_balances = True

    return {
        "client_obj": client_obj,
        "retirement_age": retirement_age,
        "retirement_date": retirement_date,
        "retirement_year": retirement_year,
        "global_pension_start_date": global_pension_start_date,
        "blocked_fields": blocked_fields,
        "employer_current_severance_total": employer_current_severance_total,
        "ignore_blocked_balances": ignore_blocked_balances,
        "blocked_field_amount": blocked_field_amount,
    }
