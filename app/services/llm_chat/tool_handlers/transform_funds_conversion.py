import json
from datetime import datetime, date
from typing import Optional

from sqlalchemy.orm import Session

from app.models import PensionFund, Scenario
from app.models.capital_asset import CapitalAsset
from app.services.pension_portfolio.conversion_rules import (
    preferred_conversion_type_for_component,
    validate_component_conversion,
)


def _delete_existing_tool_created_records(
    *,
    db: Session,
    client_id: int,
    account_number: str,
    delete_pensions: bool,
    delete_capitals: bool,
) -> None:
    if not account_number:
        return

    if delete_pensions:
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

    if delete_capitals:
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


def _preferred_conversion_type_for_component(*, field: str, product_type: str) -> str:
    return preferred_conversion_type_for_component(field=field, product_type=product_type)


def _validate_component_conversion(
    *, field: str, amount: float, conversion_type: str, product_type: str
) -> tuple[bool, str | None, str | None]:
    return validate_component_conversion(
        field=field, amount=amount, conversion_type=conversion_type, product_type=product_type
    )


def _derive_capital_tax_treatment_from_components(*, components: dict, product_type: str) -> Optional[str]:
    if not isinstance(components, dict) or not components:
        return None

    taxes: set[str] = set()
    for field, value in components.items():
        try:
            amount = float(value or 0)
        except (TypeError, ValueError):
            amount = 0.0
        if amount <= 0:
            continue

        ok, tax, _err = validate_component_conversion(
            field=str(field),
            amount=amount,
            conversion_type="capital_asset",
            product_type=product_type,
        )
        if ok and tax:
            taxes.add(str(tax))

    if not taxes:
        return None
    if "taxable" in taxes:
        return "taxable"
    if "tax_spread" in taxes:
        return "tax_spread"
    if "capital_gains" in taxes:
        return "capital_gains"
    if "fixed_rate" in taxes:
        return "fixed_rate"
    if "exempt" in taxes:
        return "exempt"
    return next(iter(taxes))


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
    zero_epsilon = 0.01
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
            for field, raw_delta in list(fields.items()):
                if field in protected_fields:
                    continue
                delta_val = _coerce_float(raw_delta)
                if delta_val <= 0:
                    continue
                current_val = _coerce_float(row.get(field))
                remaining_val = max(0.0, current_val - delta_val)
                row[field] = 0.0 if remaining_val <= zero_epsilon else remaining_val

        prior_balance = None
        if "יתרה" in row:
            prior_balance = _coerce_float(row.get("יתרה"))
            remaining = max(0.0, prior_balance - total)
            row["יתרה"] = 0.0 if remaining <= zero_epsilon else remaining
        if "balance" in row:
            if prior_balance is None:
                prior_balance = _coerce_float(row.get("balance"))
            remaining = max(0.0, _coerce_float(row.get("balance")) - total)
            row["balance"] = 0.0 if remaining <= zero_epsilon else remaining

        if prior_balance is not None:
            if max(0.0, prior_balance - total) <= zero_epsilon:
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
        aggregate_key = None
        if "סך_תגמולים" in normalized:
            aggregate_key = "סך_תגמולים"
        elif "תגמולים" in normalized:
            aggregate_key = "תגמולים"

        if aggregate_key:
            try:
                aggregate_val = float(normalized.get(aggregate_key) or 0)
            except (TypeError, ValueError):
                aggregate_val = 0.0

            granular_sum = 0.0
            for k in granular_keys:
                try:
                    granular_sum += float(normalized.get(k) or 0)
                except (TypeError, ValueError):
                    continue

            remainder = aggregate_val - granular_sum
            if remainder > 0.01:
                normalized[aggregate_key] = remainder
            else:
                normalized.pop(aggregate_key, None)

        # Ensure we don't keep both aggregate variants after the remainder calculation
        if aggregate_key == "סך_תגמולים":
            normalized.pop("תגמולים", None)
        elif aggregate_key == "תגמולים":
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
