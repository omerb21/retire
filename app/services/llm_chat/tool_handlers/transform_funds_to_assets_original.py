import json
import logging
from datetime import datetime, date
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models import PensionFund, Scenario
from app.models.capital_asset import CapitalAsset
from app.services.annuity_coefficient import get_annuity_coefficient
from app.services.llm_agent_tools_service import AgentToolsService
from app.services.llm_chat.orchestration_utils import build_transform_accounts_from_portfolio
from app.services.pension_portfolio.conversion_rules import (
    is_education_fund,
    is_investment_provident_fund,
    preferred_conversion_type_for_component,
    validate_component_conversion,
)
from app.services.retirement.utils.projection_utils import calculate_compound_factor
from app.services.retirement_age_service import calculate_retirement_age

logger = logging.getLogger("app.llm_chat.tools")


def _delete_existing_tool_created_records(*, db: Session, client_id: int, account_number: str) -> None:
    if not account_number:
        return

    pension_rows = (
        db.query(PensionFund)
        .filter(
            PensionFund.client_id == client_id,
            PensionFund.deduction_file == account_number,
            PensionFund.conversion_source.isnot(None),
            PensionFund.conversion_source.like('%%"source": "llm_transform_funds_to_assets"%%'),
        )
        .all()
    )
    for row in pension_rows:
        db.delete(row)

    capital_rows = (
        db.query(CapitalAsset)
        .filter(
            CapitalAsset.client_id == client_id,
            CapitalAsset.conversion_source.isnot(None),
            CapitalAsset.conversion_source.like('%%"source": "llm_transform_funds_to_assets"%%'),
            CapitalAsset.conversion_source.like(f'%%"account_number": "{account_number}"%%'),
        )
        .all()
    )
    for row in capital_rows:
        db.delete(row)


def classify_product_type(product_type_str: str, default_conversion_type: str = "pension") -> str:
    """Classify product type to determine conversion destination."""
    if not product_type_str:
        return default_conversion_type

    pt = (product_type_str or "").strip().lower()

    if any(token in pt for token in ("education_fund", "klal_stud")):
        return "capital_asset"

    if any(token in pt for token in ("provident_fund", "savings_policy")):
        return "capital_asset"

    if "גמל להשקעה" in pt:
        return "capital_asset"

    if "השתלמות" in pt:
        return "capital_asset"

    if "פוליסת חיסכון" in pt and "טהור" in pt:
        return "capital_asset"

    if "ביטוח" in pt:
        return "pension"

    if "קרן פנסיה" in pt or "פנסיה" in pt:
        return "pension"

    # 'קופת גמל' can be either annuity-oriented or capital-oriented. We only classify
    # as pension when annuity intent is explicit.
    if "קופת גמל" in pt and ("לקצבה" in pt or "קצבה" in pt):
        return "pension"
    if "קופת גמל" in pt:
        return "pension"

    if "חיסכון" in pt:
        return "capital_asset"

    return default_conversion_type


def _preferred_conversion_type_for_component(*, field: str, product_type: str) -> str:
    return preferred_conversion_type_for_component(field=field, product_type=product_type)


def _validate_component_conversion(
    *, field: str, amount: float, conversion_type: str, product_type: str
) -> tuple[bool, str | None, str | None]:
    return validate_component_conversion(
        field=field, amount=amount, conversion_type=conversion_type, product_type=product_type
    )


def _is_education_fund(product_type: str) -> bool:
    return is_education_fund(product_type)


def _zero_source_portfolio_pension_funds(
    *,
    db: Session,
    client_id: int,
    account_number: str,
) -> int:
    if not account_number:
        return 0

    source_funds = (
        db.query(PensionFund)
        .filter(
            PensionFund.client_id == client_id,
            PensionFund.deduction_file == account_number,
            PensionFund.conversion_source.isnot(None),
        )
        .filter(~PensionFund.conversion_source.like('%%"source": "llm_transform_funds_to_assets"%%'))
        .filter(
            (PensionFund.conversion_source.like('%"source": "pension_portfolio"%'))
            | (PensionFund.conversion_source.like('%"type": "pension_portfolio"%'))
            | (PensionFund.conversion_source.like('%"source": "pension_portfolio_convert"%'))
        )
        .all()
    )

    updated = 0
    for pf in source_funds:
        balance_val = float(pf.balance or 0)
        pension_val = float(pf.pension_amount or 0)
        if balance_val != 0.0 or pension_val != 0.0:
            pf.balance = 0.0
            pf.pension_amount = 0.0
            updated += 1
    return updated


def _coerce_float(value) -> float:
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


def _apply_snapshot_deltas(*, portfolio: list[dict], deltas: dict[str, dict]) -> list[dict]:
    updated: list[dict] = []
    for item in portfolio:
        if not isinstance(item, dict):
            continue
        row = dict(item)
        account_number = str(
            row.get("מספר_חשבון")
            or row.get("account_number")
            or row.get("מספר חשבון")
            or ""
        ).strip()
        if not account_number or account_number not in deltas:
            updated.append(row)
            continue

        delta = deltas.get(account_number) or {}
        fields = delta.get("fields") or {}
        total = _coerce_float(delta.get("total"))

        protected_fields = {
            "פיצויים_מעסיק_נוכחי",
            "פיצויים_שלא_עברו_התחשבנות",
            "פיצויים_ממעסיקים_קודמים_רצף_זכויות",
        }
        component_prefixes = ("תגמולי_", "פיצויים_")
        component_exact = {"תגמולים", "סך_תגמולים", "סך_פיצויים", "סך_רכיבים", "קרן_השתלמות"}

        if fields and isinstance(fields, dict):
            for field in list(fields.keys()):
                if field in row and field not in protected_fields:
                    row[field] = 0

        prior_balance = None
        if "יתרה" in row:
            prior_balance = _coerce_float(row.get("יתרה"))
            row["יתרה"] = max(0.0, prior_balance - total)
        if "balance" in row:
            if prior_balance is None:
                prior_balance = _coerce_float(row.get("balance"))
            row["balance"] = max(0.0, _coerce_float(row.get("balance")) - total)

        if (not fields or not isinstance(fields, dict) or not fields) and (prior_balance is not None):
            if max(0.0, prior_balance - total) == 0.0:
                for key in list(row.keys()):
                    if key in protected_fields:
                        continue
                    if key.startswith(component_prefixes) or key in component_exact:
                        row[key] = 0

        updated.append(row)
    return updated


def _create_updated_snapshot_scenario(
    *,
    db: Session,
    client_id: int,
    deltas: dict[str, dict],
) -> tuple[bool, int]:
    if not deltas:
        return True, 0

    snapshot = (
        db.query(Scenario)
        .filter(Scenario.client_id == client_id)
        .filter(Scenario.scenario_name == "pension_portfolio_snapshot")
        .order_by(Scenario.created_at.desc())
        .first()
    )
    if snapshot is None or not snapshot.parameters:
        return False, 0

    try:
        params = json.loads(snapshot.parameters)
    except Exception:
        return False, 0

    portfolio = params.get("pension_portfolio")
    if not isinstance(portfolio, list) or not portfolio:
        return False, 0

    updated_portfolio = _apply_snapshot_deltas(portfolio=portfolio, deltas=deltas)
    if not updated_portfolio:
        return False, 0

    new_params = dict(params)
    new_params["pension_portfolio"] = updated_portfolio

    scenario = Scenario(
        client_id=client_id,
        scenario_name="pension_portfolio_snapshot",
        apply_tax_planning=False,
        apply_capitalization=False,
        apply_exemption_shield=False,
        parameters=json.dumps(new_params, ensure_ascii=False),
    )
    db.add(scenario)
    return True, 1


def _parse_date_value(value) -> Optional[date]:
    if value is None:
        return None

    raw = str(value).strip()
    if not raw:
        return None

    try:
        return date.fromisoformat(raw)
    except ValueError:
        pass

    for fmt in ("%d/%m/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except Exception:
            continue

    return None


def _normalize_specific_amounts(specific_amounts: dict) -> dict[str, float]:
    if not isinstance(specific_amounts, dict):
        return {}

    normalized: dict[str, float] = {}
    for k, v in specific_amounts.items():
        try:
            val = float(v or 0)
        except (TypeError, ValueError):
            val = 0.0
        if val > 0:
            normalized[str(k)] = val

    if "קרן_השתלמות" in normalized:
        normalized.pop("תגמולים", None)
        normalized.pop("סך_תגמולים", None)
        for key in [k for k in list(normalized.keys()) if k.startswith("תגמולי_")]:
            normalized.pop(key, None)

    if "סך_תגמולים" in normalized and "תגמולים" in normalized:
        if normalized["סך_תגמולים"] >= normalized["תגמולים"]:
            normalized.pop("תגמולים", None)
        else:
            normalized.pop("סך_תגמולים", None)

    granular_keys = [k for k in normalized.keys() if k.startswith("תגמולי_")]
    if granular_keys:
        normalized.pop("תגמולים", None)
        normalized.pop("סך_תגמולים", None)

    return normalized


def _build_specific_amounts_from_account(account: dict) -> dict[str, float]:
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

    specific_amounts: dict[str, float] = {}
    for field in component_fields:
        if field not in account:
            continue
        raw_val = account.get(field)
        try:
            val = float(raw_val or 0)
        except (TypeError, ValueError):
            val = 0.0
        if val > 0:
            specific_amounts[field] = val

    return _normalize_specific_amounts(specific_amounts)


def _derive_conversion_type_from_components(*, specific_amounts: dict[str, float]) -> str | None:
    if not specific_amounts:
        return None

    pension_fields = {
        "פיצויים_ממעסיקים_קודמים_רצף_קצבה",
        "תגמולי_עובד_אחרי_2000",
        "תגמולי_מעביד_אחרי_2000",
        "תגמולי_עובד_אחרי_2008_לא_משלמת",
        "תגמולי_מעביד_אחרי_2008_לא_משלמת",
    }
    capital_fields = {
        "תגמולי_עובד_עד_2000",
        "תגמולי_מעביד_עד_2000",
        "קרן_השתלמות",
        "פיצויים_לאחר_התחשבנות",
    }

    pension_sum = sum(float(specific_amounts.get(k) or 0) for k in pension_fields)
    capital_sum = sum(float(specific_amounts.get(k) or 0) for k in capital_fields)

    if pension_sum > 0 and capital_sum == 0:
        return "pension"
    if capital_sum > 0 and pension_sum == 0:
        return "capital_asset"
    if pension_sum > 0 and capital_sum > 0:
        return "pension"
    return None


def _is_allowed_capital_without_breakdown(*, product_type: str, account_name: str) -> bool:
    candidate = f"{product_type or ''} {account_name or ''}".lower()
    return any(
        token in candidate
        for token in (
            "השתלמות",
            "גמל להשקעה",
            "קופת גמל",
            "חיסכון",
            "פוליסת חיסכון",
            "education_fund",
            "klal_stud",
            "provident_fund",
            "savings_policy",
            "savings",
            "policy",
        )
    )


def handle_transform_funds_to_assets(
    *,
    args: dict,
    client_id: int,
    db: Session,
    agent_tools: AgentToolsService,
) -> str:
    logger.info("🔄 TRANSFORM_FUNDS_TO_ASSETS called - Converting funds to assets")

    try:
        accounts = args.get("accounts", [])
        pension_start_date_raw = args.get("pension_start_date")
        default_conversion_type = args.get("default_conversion_type", "pension")
        ignore_blocked_balances = bool(args.get("ignore_blocked_balances"))
        skip_non_convertible_accounts = bool(args.get("skip_non_convertible_accounts"))
        use_provided_accounts_only = bool(args.get("use_provided_accounts_only"))

        def _is_aggregate_account(acc: dict) -> bool:
            name = str(acc.get("account_name") or acc.get("שם_תכנית") or "")
            number = str(acc.get("account_number") or acc.get("מספר_חשבון") or "")
            product_type = str(acc.get("product_type") or acc.get("סוג_מוצר") or "")
            return (
                name.startswith("Aggregate_")
                or number.startswith("AGG-")
                or product_type.startswith("aggregate_")
            )

        portfolio = getattr(agent_tools, "pension_portfolio_data", None)
        derived_accounts = build_transform_accounts_from_portfolio(portfolio)

        if (not use_provided_accounts_only) and derived_accounts:
            provided_numbers = {
                str(a.get("account_number") or a.get("מספר_חשבון") or "").strip()
                for a in accounts
                if isinstance(a, dict)
            }
            derived_numbers = {
                str(a.get("account_number") or a.get("מספר_חשבון") or "").strip()
                for a in derived_accounts
                if isinstance(a, dict)
            }
            provided_numbers.discard("")
            derived_numbers.discard("")

            should_replace = (not accounts) or (len(derived_accounts) > len(accounts))
            if derived_numbers and provided_numbers and not derived_numbers.issubset(provided_numbers):
                should_replace = True

            if should_replace:
                logger.info(
                    "🔁 Using derived portfolio accounts for transform (client_id=%s, provided=%s, derived=%s)",
                    client_id,
                    len(accounts) if isinstance(accounts, list) else 0,
                    len(derived_accounts),
                )
                accounts = derived_accounts

        if isinstance(accounts, list) and accounts:
            if any(_is_aggregate_account(a) for a in accounts if isinstance(a, dict)):
                if derived_accounts:
                    logger.info(
                        "🔁 Replacing aggregate accounts with derived portfolio accounts (client_id=%s, aggregates=%s, derived=%s)",
                        client_id,
                        len([a for a in accounts if isinstance(a, dict) and _is_aggregate_account(a)]),
                        len(derived_accounts),
                    )
                    accounts = derived_accounts

        if not accounts or not isinstance(accounts, list):
            return json.dumps(
                {
                    "success": False,
                    "error": "חסרה רשימת חשבונות להמרה (accounts)",
                    "total_converted": 0,
                    "converted_pensions": 0,
                    "converted_capitals": 0,
                },
                ensure_ascii=False,
            )

        from decimal import Decimal
        from datetime import date as date_type

        client_obj = getattr(agent_tools, "client", None)
        retirement_age = 67
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

        global_pension_start_date = _parse_date_value(pension_start_date_raw)

        converted_pensions = 0
        converted_capitals = 0
        skipped_accounts = 0
        errors = []

        source_pension_funds_zeroed = 0

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
                        blocked_field_amount += val
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
            return json.dumps(
                {
                    "success": False,
                    "error": (
                        "לא ניתן להמשיך בתרחיש כל עוד קיימות יתרות בעמודות "
                        "'פיצויים שלא עברו התחשבנות' או 'רצף פיצויים מעסיקים קודמים (זכויות)'. "
                        "נא לבצע התחשבנות ולרוקן עמודות אלו לפני המשך התרחיש."
                    ),
                    "blocked": {
                        "unresolved_severance_total": unresolved_severance_total,
                        "rights_sequence_total": rights_sequence_total,
                    },
                    "total_converted": 0,
                    "converted_pensions": 0,
                    "converted_capitals": 0,
                },
                ensure_ascii=False,
            )

        conversion_tasks: list[dict] = []
        converted_items: list[dict] = []
        skipped_items: list[dict] = []

        validation_errors: list[str] = []

        skipped_non_convertible: list[dict[str, str]] = []

        for idx, account in enumerate(accounts):
            if not isinstance(account, dict):
                validation_errors.append(f"חשבון {idx + 1}: פורמט חשבון לא תקין")
                continue

            account_name = account.get("account_name") or account.get("שם_תכנית", f"חשבון {idx + 1}")
            product_type = account.get("product_type") or account.get("סוג_מוצר", "")
            rules_product_type = f"{product_type or ''} {account_name or ''}".strip()
            account_number = account.get("account_number") or account.get("מספר_חשבון") or ""
            if not str(account_number).strip():
                validation_errors.append(f"{account_name}: חסר מספר חשבון (מספר_חשבון) ולכן לא ניתן לבצע המרה בטוחה")
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
                    "יש לבצע PROCESS_TERMINATION במסך מעסיק נוכחי."
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
                (isinstance(account.get("specific_amounts"), dict) and bool(account.get("specific_amounts")))
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
                capital_components: dict[str, float] = {}

                for field, val in list(specific_amounts.items()):
                    try:
                        numeric_val = float(val or 0)
                    except (TypeError, ValueError):
                        numeric_val = 0.0
                    if numeric_val <= 0:
                        continue

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
                        else:
                            msg = err_msg2 or err_msg or f"לא ניתן להמיר רכיב {field}"
                            if skip_non_convertible_accounts:
                                skipped_non_convertible.append(
                                    {"account_name": account_name, "reason": f"{msg} ({field})"}
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
                        pension_components[field] = float(pension_components.get(field, 0) + numeric_val)
                    else:
                        capital_components[field] = float(capital_components.get(field, 0) + numeric_val)

                pension_sum = sum(pension_components.values())
                capital_sum = sum(capital_components.values())

                if pension_sum <= 0 and capital_sum <= 0:
                    skipped_accounts += 1
                    continue

                if pension_sum > 0:
                    conversion_tasks.append(
                        {
                            "task_type": "pension",
                            "account": account,
                            "account_name": account_name,
                            "product_type": product_type,
                            "company": account.get("company") or account.get("חברה_מנהלת", ""),
                            "account_number": str(account_number).strip(),
                            "amount": pension_sum,
                            "components": pension_components,
                        }
                    )

                if capital_sum > 0:
                    conversion_tasks.append(
                        {
                            "task_type": "capital_asset",
                            "account": account,
                            "account_name": account_name,
                            "product_type": product_type,
                            "company": account.get("company") or account.get("חברה_מנהלת", ""),
                            "account_number": str(account_number).strip(),
                            "amount": capital_sum,
                            "components": capital_components,
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
                msg = (
                    f"{account_name}: אין פירוט רכיבים ולכן אסור להמיר מוצר קצבתי (ולהפריד פיצויים חסומים/הוניים) באופן בטוח"
                )
                if skip_non_convertible_accounts:
                    skipped_non_convertible.append({"account_name": account_name, "reason": msg})
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
                    msg = (
                        f"{account_name}: אין פירוט רכיבים ולכן אסור להמיר להון עבור סוג מוצר זה ({product_type})"
                    )
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

        if validation_errors:
            return json.dumps(
                {
                    "success": False,
                    "error": "שגיאות ולידציה בהמרה",
                    "validation_errors": validation_errors,
                    "total_converted": 0,
                    "converted_pensions": 0,
                    "converted_capitals": 0,
                },
                ensure_ascii=False,
            )

        deleted_for_accounts: set[str] = set()
        source_zeroed_for_accounts: set[str] = set()
        snapshot_deltas: dict[str, dict] = {}

        for idx, task in enumerate(conversion_tasks):
            try:
                account = task.get("account") or {}
                account_name = task.get("account_name")
                base_amount = float(task.get("amount") or 0)
                product_type = task.get("product_type")
                rules_product_type = f"{product_type or ''} {account_name or ''}".strip()
                company = task.get("company")
                conversion_type = task.get("task_type")
                components = task.get("components")

                account_pension_start_date_raw = (
                    account.get("pension_start_date")
                    or account.get("תאריך_מימוש")
                    or account.get("תאריך מימוש")
                )
                effective_pension_start_date = _parse_date_value(account_pension_start_date_raw) or global_pension_start_date
                if effective_pension_start_date is None:
                    effective_pension_start_date = retirement_date or date_type(retirement_year, 1, 1)

                projection_factor = 1.0
                if effective_pension_start_date and effective_pension_start_date > date_type.today():
                    try:
                        projection_factor = calculate_compound_factor(
                            from_date=date_type.today(),
                            to_date=effective_pension_start_date,
                        )
                    except Exception:
                        projection_factor = 1.0

                if conversion_type == "pension":
                    balance = float(base_amount) * float(projection_factor)
                else:
                    balance = float(base_amount)

                logger.info(
                    "🔄 Converting account: name=%s, type=%s, balance=%.2f -> %s",
                    account_name,
                    product_type,
                    balance,
                    conversion_type,
                )

                account_number = task.get("account_number") or ""
                if account_number and account_number not in deleted_for_accounts:
                    _delete_existing_tool_created_records(
                        db=db,
                        client_id=client_id,
                        account_number=account_number,
                    )
                    deleted_for_accounts.add(account_number)

                if conversion_type == "pension":
                    # Convert to pension fund
                    tax_treatment = (
                        "exempt"
                        if is_education_fund(rules_product_type)
                        or is_investment_provident_fund(rules_product_type)
                        else "taxable"
                    )

                    account_number = account_number

                    start_date_raw = (
                        account.get("start_date")
                        or account.get("תאריך_התחלה")
                        or account.get("תאריך התחלה")
                    )
                    start_date_obj = _parse_date_value(start_date_raw)

                    annuity_factor = 200.0
                    coeff = None
                    try:
                        coeff = get_annuity_coefficient(
                            product_type=product_type,
                            start_date=start_date_obj or date_type(retirement_year, 1, 1),
                            gender=getattr(client_obj, "gender", None) or "זכר",
                            retirement_age=retirement_age,
                            company_name=company or None,
                            option_name=None,
                            survivors_option="תקנוני",
                            spouse_age_diff=0,
                            target_year=effective_pension_start_date.year if effective_pension_start_date else retirement_year,
                            birth_date=getattr(client_obj, "birth_date", None),
                            pension_start_date=effective_pension_start_date,
                        )
                        annuity_factor = float(coeff.get("factor_value") or annuity_factor)
                        if annuity_factor <= 0:
                            annuity_factor = 200.0
                        logger.info(
                            "📊 Annuity coefficient resolved: client_id=%s, account='%s', product_type='%s', company='%s', start_date='%s', retirement_age=%s -> factor=%s (source=%s)",
                            client_id,
                            account_name,
                            product_type,
                            company,
                            start_date_raw,
                            retirement_age,
                            annuity_factor,
                            coeff.get("source_table") if isinstance(coeff, dict) else None,
                        )
                    except Exception as e:
                        logger.warning(
                            "⚠️ Failed to resolve annuity coefficient (fallback=200): client_id=%s, account='%s', product_type='%s', company='%s', start_date='%s': %s",
                            client_id,
                            account_name,
                            product_type,
                            company,
                            start_date_raw,
                            e,
                        )

                    pension_amount = balance / annuity_factor

                    conversion_source_json = json.dumps(
                        {
                            "source": "llm_transform_funds_to_assets",
                            "type": "pension_portfolio",
                            "account_number": account_number,
                            "account_name": account_name,
                            "company": company,
                            "product_type": product_type,
                            "start_date": start_date_raw,
                            "pension_start_date": effective_pension_start_date.isoformat() if effective_pension_start_date else None,
                            "original_amount": base_amount,
                            "projection_factor": projection_factor,
                            "components": components,
                            "resolved_annuity_factor": annuity_factor,
                            "coeff_source_table": coeff.get("source_table") if isinstance(coeff, dict) else None,
                            "converted_at": datetime.now().isoformat(),
                        },
                        ensure_ascii=False,
                    )

                    existing_pf = None
                    if account_number:
                        existing_pf = (
                            db.query(PensionFund)
                            .filter(
                                PensionFund.client_id == client_id,
                                PensionFund.deduction_file == account_number,
                                PensionFund.conversion_source.like(
                                    '%"source": "llm_transform_funds_to_assets"%'
                                ),
                            )
                            .first()
                        )

                    if existing_pf is None and account_number:
                        # Backfill scenario: previous runs may have created records with empty deduction_file.
                        # Try to find a single matching record by stable properties and update it.
                        existing_pf = (
                            db.query(PensionFund)
                            .filter(
                                PensionFund.client_id == client_id,
                                PensionFund.deduction_file.is_(None),
                                PensionFund.fund_name == account_name,
                                PensionFund.fund_type == (product_type or "קרן פנסיה"),
                                PensionFund.balance == balance,
                                PensionFund.conversion_source.like(
                                    '%"source": "llm_transform_funds_to_assets"%'
                                ),
                            )
                            .first()
                        )

                    if existing_pf:
                        existing_pf.fund_name = account_name
                        existing_pf.fund_type = product_type or existing_pf.fund_type
                        existing_pf.input_mode = "manual"
                        existing_pf.balance = balance
                        existing_pf.annuity_factor = annuity_factor
                        existing_pf.pension_amount = pension_amount
                        existing_pf.pension_start_date = effective_pension_start_date
                        existing_pf.indexation_method = "none"
                        existing_pf.tax_treatment = tax_treatment
                        if account_number:
                            existing_pf.deduction_file = account_number
                        existing_pf.conversion_source = conversion_source_json
                        existing_pf.remarks = f"הומר מתיק פנסיוני - {company}"
                    else:
                        pf = PensionFund(
                            client_id=client_id,
                            fund_name=account_name,
                            fund_type=product_type or "קרן פנסיה",
                            input_mode="manual",
                            balance=balance,
                            annuity_factor=annuity_factor,
                            pension_amount=pension_amount,
                            pension_start_date=effective_pension_start_date,
                            indexation_method="none",
                            tax_treatment=tax_treatment,
                            deduction_file=account_number or None,
                            conversion_source=conversion_source_json,
                            remarks=f"הומר מתיק פנסיוני - {company}",
                        )
                        db.add(pf)
                    db.flush()

                    if account_number and account_number not in source_zeroed_for_accounts:
                        source_pension_funds_zeroed += _zero_source_portfolio_pension_funds(
                            db=db,
                            client_id=client_id,
                            account_number=account_number,
                        )
                        source_zeroed_for_accounts.add(account_number)

                    if account_number:
                        entry = snapshot_deltas.setdefault(
                            str(account_number).strip(),
                            {"total": 0.0, "fields": {}},
                        )
                        entry["total"] = float(entry.get("total") or 0.0) + float(base_amount or 0.0)
                        if isinstance(components, dict) and components:
                            fields = entry.get("fields")
                            if not isinstance(fields, dict):
                                fields = {}
                            for k, v in components.items():
                                try:
                                    numeric = float(v or 0)
                                except (TypeError, ValueError):
                                    numeric = 0.0
                                if numeric > 0:
                                    fields[str(k)] = float(fields.get(str(k), 0.0)) + numeric
                            entry["fields"] = fields
                    converted_pensions += 1

                    converted_items.append(
                        {
                            "kind": "pension",
                            "account_name": account_name,
                            "account_number": account_number,
                            "amount": balance,
                            "original_amount": base_amount,
                            "projection_factor": projection_factor,
                            "pension_start_date": effective_pension_start_date.isoformat() if effective_pension_start_date else None,
                            "annuity_factor": annuity_factor,
                            "coeff_source_table": coeff.get("source_table") if isinstance(coeff, dict) else None,
                            "components": components,
                        }
                    )

                else:  # capital_asset
                    # Convert to capital asset
                    # Determine asset type based on product
                    product_lower = (rules_product_type or "").lower()

                    if is_education_fund(rules_product_type):
                        asset_type = "education_fund"
                        tax_treatment = "exempt"
                    elif is_investment_provident_fund(rules_product_type):
                        asset_type = "provident_fund"
                        tax_treatment = "capital_gains"
                    elif ("גמל" in (product_type or "")) or ("provident_fund" in product_lower):
                        asset_type = "provident_fund"
                        tax_treatment = "taxable"
                    else:
                        asset_type = "savings_account"
                        tax_treatment = "taxable"

                    account_number = account_number

                    start_date_raw = (
                        account.get("start_date")
                        or account.get("תאריך_התחלה")
                        or account.get("תאריך התחלה")
                    )
                    start_date_obj: Optional[date_type] = _parse_date_value(start_date_raw)
                    payment_date = effective_pension_start_date

                    conversion_source_json = json.dumps(
                        {
                            "source": "llm_transform_funds_to_assets",
                            "type": "pension_portfolio",
                            "account_number": account_number,
                            "account_name": account_name,
                            "company": company,
                            "product_type": product_type,
                            "start_date": start_date_raw,
                            "pension_start_date": payment_date.isoformat() if payment_date else None,
                            "original_amount": base_amount,
                            "projection_factor": projection_factor,
                            "components": components,
                            "converted_at": datetime.now().isoformat(),
                        },
                        ensure_ascii=False,
                    )

                    existing_ca = None
                    if account_number:
                        existing_ca = (
                            db.query(CapitalAsset)
                            .filter(
                                CapitalAsset.client_id == client_id,
                                CapitalAsset.conversion_source.isnot(None),
                                CapitalAsset.conversion_source.like(
                                    '%"source": "llm_transform_funds_to_assets"%'
                                ),
                                CapitalAsset.conversion_source.like(
                                    f'%"account_number": "{account_number}"%'
                                ),
                            )
                            .first()
                        )

                    if existing_ca is None and account_number:
                        # Backfill scenario: previous runs may have created capital assets without conversion_source.
                        existing_ca = (
                            db.query(CapitalAsset)
                            .filter(
                                CapitalAsset.client_id == client_id,
                                CapitalAsset.conversion_source.is_(None),
                                CapitalAsset.asset_name == account_name,
                                CapitalAsset.asset_type == asset_type,
                                or_(
                                    CapitalAsset.current_value == Decimal(str(balance)),
                                    CapitalAsset.monthly_income == Decimal(str(balance)),
                                ),
                                or_(
                                    CapitalAsset.start_date == payment_date,
                                    CapitalAsset.start_date == (start_date_obj or payment_date),
                                    CapitalAsset.start_date == date_type(2025, 1, 1),
                                ),
                            )
                            .first()
                        )

                    if existing_ca:
                        existing_ca.asset_name = account_name
                        existing_ca.asset_type = asset_type
                        existing_ca.current_value = Decimal("0")
                        existing_ca.monthly_income = Decimal(str(balance))
                        existing_ca.annual_return_rate = Decimal("0.03")
                        existing_ca.payment_frequency = "monthly"
                        existing_ca.start_date = payment_date
                        existing_ca.indexation_method = "none"
                        existing_ca.tax_treatment = tax_treatment
                        existing_ca.description = f"הומר מתיק פנסיוני - {company}"
                        existing_ca.conversion_source = conversion_source_json
                    else:
                        ca = CapitalAsset(
                            client_id=client_id,
                            asset_name=account_name,
                            asset_type=asset_type,
                            current_value=Decimal("0"),
                            monthly_income=Decimal(str(balance)),
                            annual_return_rate=Decimal("0.03"),
                            payment_frequency="monthly",
                            start_date=payment_date,
                            indexation_method="none",
                            tax_treatment=tax_treatment,
                            conversion_source=conversion_source_json,
                            description=f"הומר מתיק פנסיוני - {company}",
                        )
                        db.add(ca)
                    db.flush()

                    if account_number and account_number not in source_zeroed_for_accounts:
                        source_pension_funds_zeroed += _zero_source_portfolio_pension_funds(
                            db=db,
                            client_id=client_id,
                            account_number=account_number,
                        )
                        source_zeroed_for_accounts.add(account_number)

                    if account_number:
                        entry = snapshot_deltas.setdefault(
                            str(account_number).strip(),
                            {"total": 0.0, "fields": {}},
                        )
                        entry["total"] = float(entry.get("total") or 0.0) + float(base_amount or 0.0)
                        if isinstance(components, dict) and components:
                            fields = entry.get("fields")
                            if not isinstance(fields, dict):
                                fields = {}
                            for k, v in components.items():
                                try:
                                    numeric = float(v or 0)
                                except (TypeError, ValueError):
                                    numeric = 0.0
                                if numeric > 0:
                                    fields[str(k)] = float(fields.get(str(k), 0.0)) + numeric
                            entry["fields"] = fields
                    converted_capitals += 1

                    converted_items.append(
                        {
                            "kind": "capital_asset",
                            "account_name": account_name,
                            "account_number": account_number,
                            "amount": balance,
                            "original_amount": base_amount,
                            "projection_factor": projection_factor,
                            "start_date": payment_date.isoformat() if payment_date else None,
                            "components": components,
                        }
                    )

            except Exception as acc_err:
                errors.append(f"שגיאה בחשבון {account_name}: {str(acc_err)}")
                logger.error("Error converting account %s: %s", account_name, acc_err)

        total_converted = converted_pensions + converted_capitals

        scenario_source_cleanup_ok = None
        scenarios_updated = 0

        try:
            scenario_source_cleanup_ok, scenarios_updated = _create_updated_snapshot_scenario(
                db=db,
                client_id=client_id,
                deltas=snapshot_deltas,
            )
        except Exception:
            scenario_source_cleanup_ok = False
            scenarios_updated = 0

        db.commit()

        response = {
            "success": True,
            "message": f"✅ הומרו בהצלחה {total_converted} חשבונות: {converted_pensions} נכסי קצבה, {converted_capitals} נכסי הון.",
            "converted_pensions": converted_pensions,
            "converted_capitals": converted_capitals,
            "total_converted": total_converted,
            "skipped_zero_balance": skipped_accounts,
            "skipped_non_convertible": skipped_non_convertible if skipped_non_convertible else None,
            "converted_items": converted_items if converted_items else None,
            "skipped_items": skipped_items if skipped_items else None,
            "ignored_blocked_amount": blocked_field_amount if blocked_field_amount > 0 else None,
            "employer_current_severance_not_converted": employer_current_severance_total if employer_current_severance_total > 0 else None,
            "errors": errors if errors else None,
            "next_step": "כעת ניתן להפיק דוח באמצעות GENERATE_FULL_REPORT" if total_converted > 0 else None,
            "source_data_cleared": False,
            "memory_cleared": False,
            "persisted_source_scenarios_updated": scenarios_updated,
            "persisted_source_cleanup_ok": scenario_source_cleanup_ok,
            "source_pension_funds_zeroed": source_pension_funds_zeroed,
        }

        logger.info(
            "✅ TRANSFORM_FUNDS_TO_ASSETS completed: pensions=%d, capitals=%d, skipped=%d",
            converted_pensions,
            converted_capitals,
            skipped_accounts,
        )

        return json.dumps(response, ensure_ascii=False)

    except Exception as e:
        logger.error("TRANSFORM_FUNDS_TO_ASSETS failed: %s", e, exc_info=True)
        return json.dumps(
            {
                "success": False,
                "error": f"שגיאה בהמרת הכספים: {str(e)}",
                "total_converted": 0,
                "converted_pensions": 0,
                "converted_capitals": 0,
            },
            ensure_ascii=False,
        )
