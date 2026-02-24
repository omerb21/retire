import json

from typing import Any, Optional


def maybe_clear_pension_portfolio_after_transform(
    *,
    tool_name: str | None,
    tool_result: str,
    current_pension_portfolio: Optional[list[Any]],
) -> Optional[list[Any]]:
    if tool_name != "TRANSFORM_FUNDS_TO_ASSETS":
        return current_pension_portfolio

    try:
        parsed_transform = json.loads(tool_result)
        if (
            isinstance(parsed_transform, dict)
            and parsed_transform.get("success") is True
            and parsed_transform.get("source_data_cleared") is True
        ):
            return None

    except Exception:
        return current_pension_portfolio

    return current_pension_portfolio


def build_pension_portfolio_update_after_transform(
    *,
    tool_name: str | None,
    tool_result: str,
    tool_args: dict,
    current_pension_portfolio: Optional[list[Any]],
) -> Optional[str]:
    if tool_name != "TRANSFORM_FUNDS_TO_ASSETS":
        return None

    try:
        parsed_result = json.loads(tool_result)
        if not (
            isinstance(parsed_result, dict) and parsed_result.get("success") is True
        ):
            return None
        if not parsed_result.get("total_converted"):
            return None
    except Exception:
        return None

    converted_items = parsed_result.get("converted_items")
    if not isinstance(converted_items, list) or not converted_items:
        accounts = tool_args.get("accounts") if isinstance(tool_args, dict) else None
        if not isinstance(accounts, list) or not accounts:
            return None
        converted_items = []
        for acc in accounts:
            if not isinstance(acc, dict):
                continue
            account_number = str(
                acc.get("account_number")
                or acc.get("מספר_חשבון")
                or acc.get("מספר חשבון")
                or acc.get("מספר-חשבון")
                or ""
            ).strip()
            if not account_number:
                continue
            specific_amounts_raw = acc.get("specific_amounts")
            specific_amounts = (
                specific_amounts_raw if isinstance(specific_amounts_raw, dict) else None
            )
            components = dict(specific_amounts or {})
            components.pop("פיצויים_מעסיק_נוכחי", None)
            amount = 0.0
            if components:
                try:
                    amount = float(sum(float(v or 0) for v in components.values()))
                except Exception:
                    amount = 0.0
            if amount <= 0:
                raw_balance = acc.get("balance")
                if raw_balance is None:
                    raw_balance = acc.get("יתרה")
                try:
                    amount = float(raw_balance or 0)
                except Exception:
                    amount = 0.0
            if amount <= 0:
                continue
            converted_items.append(
                {
                    "account_number": account_number,
                    "account_name": acc.get("account_name")
                    or acc.get("שם_תכנית")
                    or "",
                    "amount": amount,
                    "components": components if components else None,
                }
            )

    def _portfolio_item_to_dict(item: Any) -> dict[str, Any]:
        if isinstance(item, dict):
            return item
        model_dump = getattr(item, "model_dump", None)
        if callable(model_dump):
            dumped = model_dump()
            return dumped if isinstance(dumped, dict) else {}
        raw = getattr(item, "__dict__", {})
        return raw if isinstance(raw, dict) else {}

    portfolio_by_number: dict[str, dict[str, Any]] = {}
    for item in current_pension_portfolio or []:
        data = _portfolio_item_to_dict(item)
        num = str(
            data.get("מספר_חשבון")
            or data.get("מספר חשבון")
            or data.get("מספר-חשבון")
            or data.get("account_number")
            or ""
        ).strip()
        if num:
            portfolio_by_number[num] = data

    updates: list[dict[str, Any]] = []
    for item in converted_items:
        if not isinstance(item, dict):
            continue

        account_number = str(item.get("account_number") or "").strip()
        if not account_number:
            continue

        specific_amounts = item.get("components")
        if not isinstance(specific_amounts, dict):
            specific_amounts = None
        else:
            specific_amounts = dict(specific_amounts)
            specific_amounts.pop("פיצויים_מעסיק_נוכחי", None)
            if not specific_amounts:
                specific_amounts = None

        # Prefer component-sum when available so the UI/localStorage snapshot subtraction is consistent.
        if isinstance(specific_amounts, dict) and specific_amounts:
            try:
                converted_amount = float(
                    sum(float(v or 0) for v in specific_amounts.values())
                )
            except Exception:
                converted_amount = 0.0
        else:
            raw_original = item.get("original_amount")
            try:
                converted_amount = float(
                    raw_original
                    if raw_original is not None
                    else (item.get("amount") or 0)
                )
            except Exception:
                converted_amount = 0.0
        if converted_amount <= 0:
            continue

        portfolio_item = portfolio_by_number.get(account_number) or {}
        updates.append(
            {
                "account_number": account_number,
                "account_name": item.get("account_name")
                or portfolio_item.get("שם_תכנית")
                or portfolio_item.get("account_name")
                or "",
                "company": portfolio_item.get("חברה_מנהלת")
                or portfolio_item.get("company")
                or "",
                "converted_amount": converted_amount,
                "specific_amounts": specific_amounts,
            }
        )

    if not updates:
        return None

    payload = json.dumps(
        {
            "type": "pension_portfolio_updates",
            "updates": updates,
            "operation": "converted_to_assets",
        },
        ensure_ascii=False,
    )

    return (
        f"###PENSION_PORTFOLIO_UPDATE###{payload}###END_PENSION_PORTFOLIO_UPDATE###\n"
    )


def build_pension_portfolio_update_after_commutation(
    *,
    tool_name: str | None,
    tool_result: str,
    tool_args: dict,
    current_pension_portfolio: Optional[list[Any]],
) -> Optional[str]:
    if tool_name != "EXECUTE_PENSION_COMMUTATION":
        return None

    try:
        parsed_result = json.loads(tool_result)
        if not (
            isinstance(parsed_result, dict) and parsed_result.get("success") is True
        ):
            return None
    except Exception:
        return None

    account_number = str(
        parsed_result.get("portfolio_account_number")
        or parsed_result.get("account_number")
        or ""
    ).strip()
    if not account_number:
        return None

    try:
        converted_amount = float(parsed_result.get("commutation_amount") or 0)
    except Exception:
        converted_amount = 0.0
    if converted_amount <= 0:
        return None

    def _portfolio_item_to_dict(item: Any) -> dict[str, Any]:
        if isinstance(item, dict):
            return item
        model_dump = getattr(item, "model_dump", None)
        if callable(model_dump):
            dumped = model_dump()
            return dumped if isinstance(dumped, dict) else {}
        raw = getattr(item, "__dict__", {})
        return raw if isinstance(raw, dict) else {}

    portfolio_by_number: dict[str, dict[str, Any]] = {}
    for item in current_pension_portfolio or []:
        data = _portfolio_item_to_dict(item)
        num = str(
            data.get("מספר_חשבון")
            or data.get("מספר חשבון")
            or data.get("מספר-חשבון")
            or data.get("account_number")
            or ""
        ).strip()
        if num:
            portfolio_by_number[num] = data

    portfolio_item = portfolio_by_number.get(account_number) or {}

    updates = [
        {
            "account_number": account_number,
            "account_name": portfolio_item.get("שם_תכנית")
            or portfolio_item.get("account_name")
            or "",
            "company": portfolio_item.get("חברה_מנהלת")
            or portfolio_item.get("company")
            or "",
            "converted_amount": converted_amount,
            "specific_amounts": None,
        }
    ]

    payload = json.dumps(
        {
            "type": "pension_portfolio_updates",
            "updates": updates,
            "operation": "pension_commutation",
        },
        ensure_ascii=False,
    )

    return (
        f"###PENSION_PORTFOLIO_UPDATE###{payload}###END_PENSION_PORTFOLIO_UPDATE###\n"
    )
