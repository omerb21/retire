from __future__ import annotations

import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import PensionFund
from app.models.capital_asset import CapitalAsset
from app.services.annuity_coefficient import get_annuity_coefficient
from app.services.pension_portfolio.conversion_rules import is_education_fund, is_investment_provident_fund

from .transform_funds_conversion import (
    _derive_capital_tax_treatment_from_components,
    _parse_date_value,
    _zero_source_portfolio_pension_funds,
)

logger = logging.getLogger("app.llm_chat.tools")


def apply_conversion_task_to_snapshot(
    *,
    db: Session,
    client_id: int,
    retirement_year: int,
    retirement_age: int,
    client_obj,
    use_provided_accounts_only: bool,
    remaining_only: bool,
    task: dict,
    account: dict,
    account_name: str,
    product_type: str,
    rules_product_type: str,
    company: str,
    conversion_type: str,
    components,
    account_number: str,
    balance: float,
    base_amount: float,
    projection_factor: float,
    effective_pension_start_date,
    snapshot_deltas: dict[str, dict],
    source_zeroed_for_accounts: set[str],
    source_pension_funds_zeroed: int,
    converted_pensions: int,
    converted_capitals: int,
    converted_commutations: int,
    converted_items: list[dict],
) -> tuple[
    dict[str, dict],
    set[str],
    int,
    int,
    int,
    int,
    list[dict],
]:
    from datetime import date as date_type

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
                    PensionFund.conversion_source.like('%"source": "llm_transform_funds_to_assets"%'),
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
                    PensionFund.conversion_source.like('%"source": "llm_transform_funds_to_assets"%'),
                )
                .first()
            )

        if existing_pf:
            existing_pf.fund_name = account_name
            existing_pf.fund_type = product_type or existing_pf.fund_type
            existing_pf.input_mode = "manual"
            if remaining_only:
                try:
                    existing_pf.balance = float(existing_pf.balance or 0) + float(balance or 0)
                except Exception:
                    existing_pf.balance = balance
            else:
                existing_pf.balance = balance
            existing_pf.annuity_factor = annuity_factor
            existing_pf.pension_amount = float(existing_pf.balance or 0) / float(annuity_factor or 200.0)
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

        if (
            (not use_provided_accounts_only)
            and account_number
            and account_number not in source_zeroed_for_accounts
        ):
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
                "tax_treatment": tax_treatment,
                "components": components,
            }
        )

    elif conversion_type == "commutation":
        task_tax_override = task.get("tax_treatment")
        tax_treatment = (
            task_tax_override.strip()
            if isinstance(task_tax_override, str) and task_tax_override.strip()
            else "taxable"
        )

        start_date_raw = (
            account.get("start_date")
            or account.get("תאריך_התחלה")
            or account.get("תאריך התחלה")
        )
        start_date_obj: Optional[date_type] = _parse_date_value(start_date_raw)

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
        except Exception:
            annuity_factor = 200.0

        pension_amount = balance / annuity_factor if annuity_factor > 0 else 0.0

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
                "commutation": True,
                "resolved_annuity_factor": annuity_factor,
                "pension_amount": pension_amount,
                "tax_treatment": tax_treatment,
                "converted_at": datetime.now().isoformat(),
            },
            ensure_ascii=False,
        )

        remarks = f"COMMUTATION:account_number={account_number}&amount={balance}"

        ca = CapitalAsset(
            client_id=client_id,
            asset_name=f"הון מהיוון - {account_name}",
            asset_type="provident_fund",
            current_value=Decimal("0"),
            monthly_income=Decimal(str(balance)),
            annual_return_rate=Decimal("0"),
            payment_frequency="annually",
            start_date=effective_pension_start_date,
            indexation_method="none",
            tax_treatment=tax_treatment,
            conversion_source=conversion_source_json,
            description=f"היוון מתיק פנסיוני - {company}",
            remarks=remarks,
        )
        db.add(ca)
        db.flush()

        if (
            (not use_provided_accounts_only)
            and account_number
            and account_number not in source_zeroed_for_accounts
        ):
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
        converted_commutations += 1
        converted_items.append(
            {
                "kind": "commutation",
                "account_name": account_name,
                "account_number": account_number,
                "amount": balance,
                "original_amount": base_amount,
                "projection_factor": projection_factor,
                "start_date": effective_pension_start_date.isoformat() if effective_pension_start_date else None,
                "asset_type": "provident_fund",
                "tax_treatment": tax_treatment,
                "annuity_factor": annuity_factor,
                "coeff_source_table": coeff.get("source_table") if isinstance(coeff, dict) else None,
                "components": components,
            }
        )

    else:  # capital_asset
        # Convert to capital asset
        # Determine asset type based on product
        product_lower = (rules_product_type or "").lower()

        components_tax_treatment = None
        if isinstance(components, dict) and components:
            components_tax_treatment = _derive_capital_tax_treatment_from_components(
                components=components,
                product_type=rules_product_type,
            )

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

        if components_tax_treatment is not None:
            tax_treatment = components_tax_treatment

        task_tax_override = task.get("tax_treatment")
        if isinstance(task_tax_override, str) and task_tax_override.strip():
            tax_treatment = task_tax_override.strip()

        account_number = account_number

        start_date_raw = (
            account.get("start_date")
            or account.get("תאריך_התחלה")
            or account.get("תאריך התחלה")
        )
        start_date_obj: Optional = _parse_date_value(start_date_raw)
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
                "capital_tax_treatment": tax_treatment,
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
                    CapitalAsset.conversion_source.like('%"source": "llm_transform_funds_to_assets"%'),
                    CapitalAsset.conversion_source.like(f'%"account_number": "{account_number}"%'),
                    CapitalAsset.conversion_source.like(f'%"capital_tax_treatment": "{tax_treatment}"%'),
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
            if remaining_only:
                try:
                    existing_ca.monthly_income = Decimal(
                        str(float(existing_ca.monthly_income or 0) + float(balance))
                    )
                except Exception:
                    existing_ca.monthly_income = Decimal(str(balance))
            else:
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

        if (
            (not use_provided_accounts_only)
            and account_number
            and account_number not in source_zeroed_for_accounts
        ):
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
                "asset_type": asset_type,
                "tax_treatment": tax_treatment,
                "components": components,
            }
        )

    return (
        snapshot_deltas,
        source_zeroed_for_accounts,
        source_pension_funds_zeroed,
        converted_pensions,
        converted_capitals,
        converted_commutations,
        converted_items,
    )
