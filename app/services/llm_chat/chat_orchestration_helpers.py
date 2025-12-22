import json
from typing import Any, Callable, Optional

from app.services.llm_chat.message_utils import extract_gross_income_for_tax


def format_transform_result_for_user(*, tool_result: str) -> str:
    try:
        parsed = json.loads(tool_result)
    except Exception:
        return "בוצעה המרה, אך לא הצלחתי לקרוא את תוצאת הכלי."

    if not isinstance(parsed, dict):
        return "בוצעה המרה, אך תוצאת הכלי אינה בפורמט צפוי."

    if parsed.get("success") is not True:
        err = parsed.get("error") or "המרה נכשלה."
        return f"המרה נכשלה: {err}"

    total_converted = int(parsed.get("total_converted") or 0)
    converted_pensions = int(parsed.get("converted_pensions") or 0)
    converted_capitals = int(parsed.get("converted_capitals") or 0)

    ignored_blocked_amount = parsed.get("ignored_blocked_amount")
    employer_current_sev = parsed.get("employer_current_severance_not_converted")

    lines: list[str] = []
    lines.append("סיכום המרה הון/קצבה בתיק:")
    lines.append(f"הומרו {total_converted} חשבונות")
    lines.append(f"נכסי קצבה שנוצרו/עודכנו: {converted_pensions}")
    lines.append(f"נכסי הון שנוצרו/עודכנו: {converted_capitals}")

    if ignored_blocked_amount is not None:
        try:
            lines.append(f"יתרות חסומות שדולגו לפי הבקשה: {float(ignored_blocked_amount):,.0f} ₪")
        except Exception:
            lines.append(f"יתרות חסומות שדולגו לפי הבקשה: {ignored_blocked_amount}")

    if employer_current_sev is not None:
        try:
            lines.append(f"פיצויי מעסיק נוכחי שלא הומרו (חסימה מערכתית): {float(employer_current_sev):,.0f} ₪")
        except Exception:
            lines.append(f"פיצויי מעסיק נוכחי שלא הומרו (חסימה מערכתית): {employer_current_sev}")

    errors = parsed.get("errors")
    if isinstance(errors, list) and errors:
        lines.append("הערות/שגיאות במהלך ההמרה:")
        for item in errors[:5]:
            lines.append(f"- {item}")

    return "\n".join(lines)


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


def build_forced_document_reply(*, tool_name: str | None, tool_result: str) -> Optional[str]:
    if not (isinstance(tool_name, str) and tool_name.startswith("GENERATE_")):
        return None

    try:
        parsed_result = json.loads(tool_result)
        if isinstance(parsed_result, dict) and parsed_result.get("success") is True:
            download_url = parsed_result.get("download_url")
            open_path = parsed_result.get("open_path")
            client_id = parsed_result.get("client_id")
            status_message = (
                parsed_result.get("status_message")
                or parsed_result.get("message")
                or "המסמך הופק בהצלחה."
            )
            if isinstance(open_path, str) and open_path.strip():
                actions: list[dict[str, str]] = [
                    {
                        "type": "navigate",
                        "path": open_path.strip(),
                        "label": "פתח דוח",
                    }
                ]

                return (
                    f"###UI_ACTION###{json.dumps({'type': 'ui_actions', 'actions': actions}, ensure_ascii=False)}###END_UI_ACTION###\n"
                    f"{status_message}"
                )

            if isinstance(download_url, str) and download_url.strip():
                actions: list[dict[str, str]] = [
                    {
                        "type": "open_url",
                        "url": download_url.strip(),
                        "label": "פתח להורדה",
                    }
                ]

                if client_id is not None:
                    actions.append(
                        {
                            "type": "navigate",
                            "path": f"/clients/{client_id}/reports",
                            "label": "פתח עמוד דוחות",
                        }
                    )

                return (
                    f"###UI_ACTION###{json.dumps({'type': 'ui_actions', 'actions': actions}, ensure_ascii=False)}###END_UI_ACTION###\n"
                    f"{status_message}\n\nקישור להורדה: {download_url.strip()}"
                )
    except Exception:
        return None

    return None


def get_gross_for_tax_chaining(*, is_net: bool, tool_name: str | None, tool_result: str) -> Optional[float]:
    if not is_net:
        return None

    if tool_name not in {"BUILD_TARGET_PENSION_PLAN", "RUN_RETIREMENT_CASHFLOW_ANALYSIS"}:
        return None

    return extract_gross_income_for_tax(tool_name, tool_result)


def run_tax_projection_autochain(
    *,
    gross_for_tax: Optional[float],
    execute_tool_call_fn: Callable[[str, dict], str],
) -> Optional[str]:
    if gross_for_tax is None:
        return None

    if gross_for_tax <= 0:
        return None

    return execute_tool_call_fn("GET_TAX_PROJECTION", {"gross_monthly_pension": gross_for_tax})


def build_pension_portfolio_update_after_transform(
    *,
    tool_name: str | None,
    tool_result: str,
    tool_args: dict,
    current_pension_portfolio: Optional[list[Any]],
) -> Optional[str]:
    if tool_name != "TRANSFORM_FUNDS_TO_ASSETS":
        return None

    if not current_pension_portfolio:
        return None

    try:
        parsed_result = json.loads(tool_result)
        if not (isinstance(parsed_result, dict) and parsed_result.get("success") is True):
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
            account_number = str(acc.get("account_number") or acc.get("מספר_חשבון") or "").strip()
            if not account_number:
                continue
            specific_amounts_raw = acc.get("specific_amounts")
            specific_amounts = specific_amounts_raw if isinstance(specific_amounts_raw, dict) else None
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
                    "account_name": acc.get("account_name") or acc.get("שם_תכנית") or "",
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
        num = str(data.get("מספר_חשבון") or data.get("account_number") or "").strip()
        if num:
            portfolio_by_number[num] = data

    updates: list[dict[str, Any]] = []
    for item in converted_items:
        if not isinstance(item, dict):
            continue

        account_number = str(item.get("account_number") or "").strip()
        if not account_number:
            continue

        try:
            converted_amount = float(item.get("amount") or 0)
        except Exception:
            converted_amount = 0.0
        if converted_amount <= 0:
            continue

        specific_amounts = item.get("components")
        if not isinstance(specific_amounts, dict):
            specific_amounts = None
        else:
            specific_amounts = dict(specific_amounts)
            specific_amounts.pop("פיצויים_מעסיק_נוכחי", None)
            if not specific_amounts:
                specific_amounts = None

        portfolio_item = portfolio_by_number.get(account_number) or {}
        updates.append(
            {
                "account_number": account_number,
                "account_name": item.get("account_name")
                or portfolio_item.get("שם_תכנית")
                or portfolio_item.get("account_name")
                or "",
                "company": portfolio_item.get("חברה_מנהלת") or portfolio_item.get("company") or "",
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

    return f"###PENSION_PORTFOLIO_UPDATE###{payload}###END_PENSION_PORTFOLIO_UPDATE###\n"
