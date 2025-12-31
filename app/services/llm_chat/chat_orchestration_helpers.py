import json
from typing import Any, Callable, Optional

from sqlalchemy.orm import Session

from app.services.llm_chat.message_utils import extract_gross_income_for_tax
from app.models import Scenario
from app.services.pension_portfolio.conversion_rules import (
    COMPONENT_RULES,
    rule_for_tagmulim_by_product_type,
)


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
    converted_commutations = int(parsed.get("converted_commutations") or 0)

    ignored_blocked_amount = parsed.get("ignored_blocked_amount")
    employer_current_sev = parsed.get("employer_current_severance_not_converted")

    converted_items = parsed.get("converted_items")
    if not isinstance(converted_items, list):
        converted_items = []

    skipped_items = parsed.get("skipped_items")
    if not isinstance(skipped_items, list):
        skipped_items = []

    lines: list[str] = []
    lines.append("סיכום המרה הון/קצבה בתיק:")
    lines.append(f"הומרו {total_converted} חשבונות")
    lines.append(f"נכסי קצבה שנוצרו/עודכנו: {converted_pensions}")
    lines.append(f"נכסי הון שנוצרו/עודכנו: {converted_capitals}")
    if converted_commutations:
        lines.append(f"מתוכם היוון להון (רכיבים קצבתיים): {converted_commutations}")

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

    def _format_amount(value: object) -> str:
        try:
            return f"{float(value or 0):,.0f}"
        except Exception:
            return str(value)

    def _format_tax(value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            return ""
        mapping = {
            "exempt": "פטור",
            "taxable": "חייב",
            "capital_gains": "רווח הון",
            "tax_spread": "פריסת מס",
            "fixed_rate": "שיעור קבוע",
        }
        return mapping.get(value, value)

    if converted_items:
        lines.append("\nפירוט חשבונות שהומרו:")

        for it in converted_items[:20]:
            if not isinstance(it, dict):
                continue
            kind = it.get("kind")
            kind_label = "נכס" if kind else "פריט"
            if kind == "pension":
                kind_label = "יתרה שהומרה לקצבה"
            elif kind == "capital_asset":
                kind_label = "יתרה שהומרה להון"
            elif kind == "commutation":
                kind_label = "יתרה שהוּונה להון"

            account_name = it.get("account_name") or ""
            account_number = it.get("account_number") or ""
            amount = _format_amount(it.get("amount"))
            tax_label = _format_tax(it.get("tax_treatment"))

            header = f"- {account_name} ({account_number}) — {kind_label}: {amount} ₪"
            if tax_label:
                header += f" — מס: {tax_label}"
            lines.append(header)

            components = it.get("components")
            if isinstance(components, dict) and components:
                shown = 0
                for field, val in components.items():
                    try:
                        num_val = float(val or 0)
                    except Exception:
                        num_val = 0.0
                    if num_val <= 0:
                        continue
                    lines.append(f"  - {field}: {_format_amount(num_val)} ₪")
                    shown += 1
                    if shown >= 10:
                        break

        if len(converted_items) > 20:
            lines.append(f"(הוצגו 20 מתוך {len(converted_items)} חשבונות שהומרו)")

    if skipped_items:
        lines.append("\nרכיבים/חשבונות שדולגו:")
        for it in skipped_items[:15]:
            if not isinstance(it, dict):
                continue
            acc_name = it.get("account_name") or ""
            acc_num = it.get("account_number") or ""
            field = it.get("field") or ""
            amount = _format_amount(it.get("amount"))
            reason = it.get("reason") or ""
            line = f"- {acc_name} ({acc_num}) — {field}: {amount} ₪"
            if reason:
                line += f" — {reason}"
            lines.append(line)

        if len(skipped_items) > 15:
            lines.append(f"(הוצגו 15 מתוך {len(skipped_items)} פריטים שדולגו)")

    return "\n".join(lines)


def _clean_account_name_for_transform(source_name: str | None) -> str:
    raw = (source_name or "").strip()
    if not raw:
        return raw
    if "(" in raw:
        prefix = raw.split("(", 1)[0].strip()
        return prefix or raw
    return raw


def _extract_target_plan_payload_from_tool_result(tool_result: str) -> dict | None:
    marker = "###TARGET_PENSION_PLAN_DATA###"
    end_marker = "###END_TARGET_PENSION_PLAN_DATA###"
    if not isinstance(tool_result, str) or not tool_result:
        return None
    if marker not in tool_result or end_marker not in tool_result:
        return None

    start = tool_result.rfind(marker)
    end = tool_result.find(end_marker, start + len(marker))
    if start < 0 or end < 0 or end <= start:
        return None
    raw_json = tool_result[start + len(marker) : end].strip()
    if not raw_json:
        return None
    try:
        parsed = json.loads(raw_json)
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def store_latest_target_pension_plan(*, db: Session, client_id: int, tool_result: str) -> bool:
    payload = _extract_target_plan_payload_from_tool_result(tool_result)
    if not payload:
        return False

    try:
        scenario = Scenario(
            client_id=client_id,
            scenario_name="target_pension_plan",
            apply_tax_planning=False,
            apply_capitalization=False,
            apply_exemption_shield=False,
            parameters=json.dumps(payload, ensure_ascii=False),
        )
        db.add(scenario)
        db.flush()
        db.commit()
        return True
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return False


def store_pending_approval_request(
    *, db: Session, client_id: int, tool_name: str, tool_args: dict
) -> bool:
    if client_id is None:
        return False
    if not isinstance(tool_name, str) or not tool_name.strip():
        return False
    if not isinstance(tool_args, dict):
        tool_args = {}

    try:
        db.query(Scenario).filter(Scenario.client_id == client_id).filter(
            Scenario.scenario_name == "pending_approval"
        ).delete(synchronize_session=False)
        db.flush()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return False

    try:
        payload = {"tool_name": tool_name, "arguments": tool_args}
        scenario = Scenario(
            client_id=client_id,
            scenario_name="pending_approval",
            apply_tax_planning=False,
            apply_capitalization=False,
            apply_exemption_shield=False,
            parameters=json.dumps(payload, ensure_ascii=False),
        )
        db.add(scenario)
        db.flush()
        db.commit()
        return True
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return False


def load_pending_approval_request(*, db: Session, client_id: int) -> tuple[str, dict] | None:
    if client_id is None:
        return None
    try:
        row = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "pending_approval")
            .order_by(Scenario.created_at.desc())
            .first()
        )
    except Exception:
        row = None
    if row is None or not getattr(row, "parameters", None):
        return None
    try:
        parsed = json.loads(row.parameters)
    except Exception:
        return None
    if not isinstance(parsed, dict):
        return None
    tool_name = parsed.get("tool_name")
    tool_args = parsed.get("arguments")
    if not isinstance(tool_name, str) or not isinstance(tool_args, dict):
        return None
    return tool_name, tool_args


def clear_pending_approval_request(*, db: Session, client_id: int) -> bool:
    if client_id is None:
        return False
    try:
        db.query(Scenario).filter(Scenario.client_id == client_id).filter(
            Scenario.scenario_name == "pending_approval"
        ).delete(synchronize_session=False)
        db.commit()
        return True
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return False


def load_latest_target_pension_plan(*, db: Session, client_id: int) -> dict | None:
    try:
        row = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "target_pension_plan")
            .order_by(Scenario.created_at.desc())
            .first()
        )
    except Exception:
        row = None
    if row is None or not getattr(row, "parameters", None):
        return None
    try:
        parsed = json.loads(row.parameters)
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


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
                "is_pension_only": _is_pension_only_component(field=field, product_type=product_type),
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
                acc_name = _clean_account_name_for_transform(str(src.get("source_name") or ""))
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


def build_approval_request_ui_action(
    *,
    tool_name: str,
    tool_args: dict,
    reason: str,
    risk_level: str | None,
    rag_sources: list[str] | None,
) -> str:
    actions: list[dict[str, object]] = [
        {
            "type": "approval_request",
            "tool_name": tool_name,
            "arguments": tool_args,
            "reason": reason,
            "risk_level": risk_level or "",
            "rag_sources": rag_sources or [],
            "approve_label": "אשר",
            "cancel_label": "בטל",
        }
    ]

    return (
        f"###UI_ACTION###{json.dumps({'type': 'ui_actions', 'actions': actions}, ensure_ascii=False)}###END_UI_ACTION###\n"
        "נדרש אישור לפני הפעלת כלי.\n"
        f"כלי: {tool_name}\n"
        f"סיבה: {reason}"
    )


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
                converted_amount = float(sum(float(v or 0) for v in specific_amounts.values()))
            except Exception:
                converted_amount = 0.0
        else:
            raw_original = item.get("original_amount")
            try:
                converted_amount = float(raw_original if raw_original is not None else (item.get("amount") or 0))
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
        if not (isinstance(parsed_result, dict) and parsed_result.get("success") is True):
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
        num = str(data.get("מספר_חשבון") or data.get("account_number") or "").strip()
        if num:
            portfolio_by_number[num] = data

    portfolio_item = portfolio_by_number.get(account_number) or {}

    updates = [
        {
            "account_number": account_number,
            "account_name": portfolio_item.get("שם_תכנית")
            or portfolio_item.get("account_name")
            or "",
            "company": portfolio_item.get("חברה_מנהלת") or portfolio_item.get("company") or "",
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

    return f"###PENSION_PORTFOLIO_UPDATE###{payload}###END_PENSION_PORTFOLIO_UPDATE###\n"
