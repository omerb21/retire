"""Portfolio helper functions (build_*from_portfolio* helpers) for chat orchestration."""

# NOTE: This module will be filled by move-only extraction from orchestration_utils.py.
# Keep bodies 1:1 when moving functions.

import json
import re
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from typing import Any

from app.services.retirement_age_service import get_retirement_date

try:
    from app.services.retirement_age_service import DEFAULT_MALE_RETIREMENT_AGE as _DEFAULT_RETIREMENT_AGE_FALLBACK
except Exception:
    _DEFAULT_RETIREMENT_AGE_FALLBACK = 67

from app.services.llm_chat.orchestration_utils_parts.protocol import (
    apply_max_exemption_if_requested,
    build_tool_call_message_content,
    parse_tool_call_from_reply,
    validate_tool_call_protocol_for_execution,
)
from app.services.llm_chat.orchestration_utils_parts.tool_names import (
    get_tool_display_name_hebrew,
    normalize_tool_name,
)



def build_portfolio_wide_prev_employers_severance_transform_accounts_from_portfolio(
    *,
    pension_portfolio: Any,
    conversion_type: str,
) -> list[dict[str, Any]]:
    fields = ["פיצויים_ממעסיקים_קודמים_רצף_קצבה"]
    if not isinstance(pension_portfolio, list) or not pension_portfolio:
        return []

    derived = build_transform_accounts_from_portfolio(pension_portfolio)
    if not derived:
        return []

    results: list[dict[str, Any]] = []
    for acc in derived:
        if not isinstance(acc, dict):
            continue

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
            "סך_תגמולים",
            "קרן_השתלמות",
        ]

        specific_amounts = acc.get("specific_amounts") if isinstance(acc.get("specific_amounts"), dict) else {}

        selected: dict[str, float] = {}
        total = 0.0
        for f in fields:
            raw = None
            if isinstance(specific_amounts, dict):
                raw = specific_amounts.get(f)
            if raw is None:
                raw = acc.get(f)
            try:
                val = float(raw or 0)
            except Exception:
                val = 0.0
            if val > 0:
                selected[f] = float(val)
                total += float(val)

        if not selected:
            continue

        base = dict(acc)
        for k in component_fields:
            if k not in selected:
                base.pop(k, None)
        base["_partial_conversion"] = True
        base["specific_amounts"] = selected
        base["component_conversion_overrides"] = {f: str(conversion_type or "pension") for f in selected.keys()}
        try:
            base["balance"] = float(total)
            base["יתרה"] = float(total)
        except Exception:
            pass
        results.append(base)

    return results

def build_portfolio_wide_education_fund_transform_accounts_from_portfolio(
    *,
    pension_portfolio: Any,
    conversion_type: str,
) -> list[dict[str, Any]]:
    fields = ["קרן_השתלמות"]
    if not isinstance(pension_portfolio, list) or not pension_portfolio:
        return []

    derived = build_transform_accounts_from_portfolio(pension_portfolio)
    if not derived:
        return []

    results: list[dict[str, Any]] = []
    for acc in derived:
        if not isinstance(acc, dict):
            continue

        product_type = str(acc.get("product_type") or acc.get("סוג_מוצר") or "")
        account_name = str(acc.get("account_name") or acc.get("שם_תכנית") or "")
        candidate = f"{product_type} {account_name}".lower()

        if ("השתלמות" not in candidate) and ("education" not in candidate) and ("klal_stud" not in candidate):
            continue

        specific_amounts = acc.get("specific_amounts") if isinstance(acc.get("specific_amounts"), dict) else {}
        try:
            ef_val = float(specific_amounts.get("קרן_השתלמות") or acc.get("קרן_השתלמות") or 0)
        except Exception:
            ef_val = 0.0
        if ef_val <= 0:
            continue

        selected: dict[str, float] = {}
        total = 0.0
        for f in fields:
            raw = None
            if isinstance(specific_amounts, dict):
                raw = specific_amounts.get(f)
            if raw is None:
                raw = acc.get(f)
            try:
                val = float(raw or 0)
            except Exception:
                val = 0.0
            if val > 0:
                selected[f] = float(val)
                total += float(val)

        if not selected:
            continue

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
            "סך_תגמולים",
            "קרן_השתלמות",
        ]

        base = dict(acc)
        for k in component_fields:
            if k not in selected:
                base.pop(k, None)
        base["_partial_conversion"] = True
        base["specific_amounts"] = selected
        base["component_conversion_overrides"] = {f: str(conversion_type or "capital_asset") for f in selected.keys()}
        try:
            base["balance"] = float(total)
            base["יתרה"] = float(total)
        except Exception:
            pass
        results.append(base)

    return results

def build_portfolio_wide_after_settlement_severance_transform_accounts_from_portfolio(
    *,
    pension_portfolio: Any,
    conversion_type: str,
) -> list[dict[str, Any]]:
    fields = ["פיצויים_לאחר_התחשבנות"]
    if not isinstance(pension_portfolio, list) or not pension_portfolio:
        return []

    derived = build_transform_accounts_from_portfolio(pension_portfolio)
    if not derived:
        return []

    results: list[dict[str, Any]] = []
    for acc in derived:
        if not isinstance(acc, dict):
            continue

        product_type = str(acc.get("product_type") or acc.get("סוג_מוצר") or "")
        account_name = str(acc.get("account_name") or acc.get("שם_תכנית") or "")
        candidate = f"{product_type} {account_name}".lower()
        if "השתלמות" in candidate or "education" in candidate:
            continue

        specific_amounts = acc.get("specific_amounts") if isinstance(acc.get("specific_amounts"), dict) else {}
        try:
            ef_val = float(specific_amounts.get("קרן_השתלמות") or acc.get("קרן_השתלמות") or 0)
        except Exception:
            ef_val = 0.0
        if ef_val > 0:
            continue

        selected: dict[str, float] = {}
        total = 0.0
        for f in fields:
            raw = None
            if isinstance(specific_amounts, dict):
                raw = specific_amounts.get(f)
            if raw is None:
                raw = acc.get(f)
            try:
                val = float(raw or 0)
            except Exception:
                val = 0.0
            if val > 0:
                selected[f] = float(val)
                total += float(val)

        if not selected:
            continue

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
            "סך_תגמולים",
            "קרן_השתלמות",
        ]

        base = dict(acc)
        for k in component_fields:
            if k not in selected:
                base.pop(k, None)
        base["_partial_conversion"] = True
        base["specific_amounts"] = selected
        base["component_conversion_overrides"] = {f: str(conversion_type or "capital_asset") for f in selected.keys()}
        try:
            base["balance"] = float(total)
            base["יתרה"] = float(total)
        except Exception:
            pass
        results.append(base)

    return results

def build_transform_accounts_from_portfolio(pension_portfolio: Any) -> list[dict[str, Any]]:
    if not isinstance(pension_portfolio, list) or not pension_portfolio:
        return []

    def _extract_account_number(data: dict[str, Any]) -> Any:
        if not isinstance(data, dict):
            return None
        return (
            data.get("מספר_חשבון")
            or data.get("מספר חשבון")
            or data.get("account_number")
            or data.get("מספר חשבון")
            or data.get("מספר-חשבון")
        )

    def _coerce_float(value: Any) -> float:
        if value is None:
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return 0.0
            cleaned = raw.replace(",", "").replace("₪", "").replace(" ", "")
            try:
                return float(cleaned)
            except (TypeError, ValueError):
                return 0.0
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

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

        nested_specific = data.get("specific_amounts")
        if not isinstance(nested_specific, dict):
            nested_specific = {}

        account_number = _extract_account_number(data)
        account_name = data.get("שם_תכנית")
        company = data.get("חברה_מנהלת")
        product_type = data.get("סוג_מוצר")
        balance = data.get("יתרה")
        start_date = data.get("תאריך_התחלה")

        specific_amounts: dict[str, float] = {}
        for field in component_fields:
            value = data.get(field)
            if value is None and field in nested_specific:
                value = nested_specific.get(field)
            numeric = _coerce_float(value)
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
                "מספר חשבון": account_number,
                "שם_תכנית": account_name,
                "חברה_מנהלת": company,
                "סוג_מוצר": product_type,
                "יתרה": balance,
                "תאריך_התחלה": start_date,
                **{field: data.get(field) for field in component_fields if field in data},
            }
        )

    return accounts

def build_portfolio_wide_component_transform_accounts_from_portfolio(
    *,
    pension_portfolio: Any,
    fields: list[str],
    conversion_type: str,
) -> list[dict[str, Any]]:
    if not fields:
        return []
    if not isinstance(pension_portfolio, list) or not pension_portfolio:
        return []

    derived = build_transform_accounts_from_portfolio(pension_portfolio)
    if not derived:
        return []

    results: list[dict[str, Any]] = []
    for acc in derived:
        if not isinstance(acc, dict):
            continue

        product_type = str(acc.get("product_type") or acc.get("סוג_מוצר") or "")
        account_name = str(acc.get("account_name") or acc.get("שם_תכנית") or "")
        candidate = f"{product_type} {account_name}".lower()

        # Exclude education funds from portfolio-wide 'tagmulim after 2000' conversion.
        # These products are capital-like and converting them here looks like a full-portfolio conversion.
        if "השתלמות" in candidate or "education" in candidate:
            continue

        specific_amounts = acc.get("specific_amounts") if isinstance(acc.get("specific_amounts"), dict) else {}
        try:
            ef_val = float(specific_amounts.get("קרן_השתלמות") or acc.get("קרן_השתלמות") or 0)
        except Exception:
            ef_val = 0.0
        if ef_val > 0:
            continue

        selected: dict[str, float] = {}
        total = 0.0
        for f in fields:
            raw = None
            if isinstance(specific_amounts, dict):
                raw = specific_amounts.get(f)
            if raw is None:
                raw = acc.get(f)
            try:
                val = float(raw or 0)
            except Exception:
                val = 0.0
            if val > 0:
                selected[f] = float(val)
                total += float(val)

        if not selected:
            continue

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
            "סך_תגמולים",
            "קרן_השתלמות",
        ]

        base = dict(acc)
        for k in component_fields:
            if k not in selected:
                base.pop(k, None)
        base["_partial_conversion"] = True
        base["specific_amounts"] = selected
        base["component_conversion_overrides"] = {f: str(conversion_type or "pension") for f in selected.keys()}
        try:
            base["balance"] = float(total)
            base["יתרה"] = float(total)
        except Exception:
            pass
        results.append(base)

    return results

def build_partial_pension_transform_accounts_from_portfolio(
    *,
    pension_portfolio: Any,
    account_number: str,
    amount: float,
) -> list[dict[str, Any]]:
    if not account_number:
        return []
    try:
        amount_val = float(amount or 0)
    except Exception:
        amount_val = 0.0
    if amount_val <= 0:
        return []
    if not isinstance(pension_portfolio, list) or not pension_portfolio:
        return []

    matched = None
    for item in pension_portfolio:
        if not isinstance(item, dict):
            model_dump = getattr(item, "model_dump", None)
            if callable(model_dump):
                try:
                    item = model_dump()
                except Exception:
                    item = None
        if not isinstance(item, dict):
            continue
        num = str(item.get("מספר_חשבון") or item.get("account_number") or item.get("מספר חשבון") or "").strip()
        if num == str(account_number).strip():
            matched = item
            break

    if not isinstance(matched, dict):
        return []

    derived = build_transform_accounts_from_portfolio([matched])
    if not derived:
        return []

    acc = dict(derived[0])
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
        "סך_תגמולים",
        "קרן_השתלמות",
    ]
    for k in component_fields:
        acc.pop(k, None)
    acc["_partial_conversion"] = True
    acc["specific_amounts"] = {"תגמולים": float(amount_val)}
    acc["component_conversion_overrides"] = {"תגמולים": "pension"}
    try:
        acc["balance"] = float(amount_val)
        acc["יתרה"] = float(amount_val)
    except Exception:
        pass
    return [acc]

def build_targeted_component_transform_accounts_from_portfolio(
    *,
    pension_portfolio: Any,
    account_number: str,
    fields: list[str],
    conversion_type: str,
) -> list[dict[str, Any]]:
    if not account_number or not fields:
        return []
    if not isinstance(pension_portfolio, list) or not pension_portfolio:
        return []

    matched = None
    for item in pension_portfolio:
        if not isinstance(item, dict):
            model_dump = getattr(item, "model_dump", None)
            if callable(model_dump):
                try:
                    item = model_dump()
                except Exception:
                    item = None
        if not isinstance(item, dict):
            continue
        num = str(item.get("מספר_חשבון") or item.get("account_number") or item.get("מספר חשבון") or "").strip()
        if num == str(account_number).strip():
            matched = item
            break

    if not isinstance(matched, dict):
        return []

    derived = build_transform_accounts_from_portfolio([matched])
    if not derived:
        return []

    base = dict(derived[0])
    specific_amounts = base.get("specific_amounts") if isinstance(base.get("specific_amounts"), dict) else {}
    selected: dict[str, float] = {}
    total = 0.0
    for f in fields:
        raw = None
        if isinstance(specific_amounts, dict):
            raw = specific_amounts.get(f)
        if raw is None:
            raw = base.get(f)
        try:
            val = float(raw or 0)
        except Exception:
            val = 0.0
        if val > 0:
            selected[f] = float(val)
            total += float(val)

    if not selected:
        return []

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
        "סך_תגמולים",
        "קרן_השתלמות",
    ]
    for k in component_fields:
        if k not in selected:
            base.pop(k, None)
    base["_partial_conversion"] = True
    base["specific_amounts"] = selected
    base["component_conversion_overrides"] = {f: str(conversion_type or "pension") for f in selected.keys()}
    try:
        base["balance"] = float(total)
        base["יתרה"] = float(total)
    except Exception:
        pass

    return [base]

