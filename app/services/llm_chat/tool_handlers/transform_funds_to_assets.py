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
from app.services.retirement_age_service import calculate_retirement_age

logger = logging.getLogger("app.llm_chat.tools")


def _is_education_fund(product_type: str) -> bool:
    return "השתלמות" in (product_type or "")


def _validate_component_conversion(
    *,
    field: str,
    amount: float,
    conversion_type: str,
    product_type: str,
) -> tuple[bool, str | None, str | None]:
    if amount <= 0:
        return True, None, None

    pt = (product_type or "").lower()

    if "גמל להשקעה" in pt:
        if conversion_type == "capital_asset":
            return True, "capital_gains", None
        return True, "exempt", None

    if _is_education_fund(product_type):
        return True, "exempt", None

    rules: dict[str, dict[str, object]] = {
        "פיצויים_מעסיק_נוכחי": {
            "pension": False,
            "capital_asset": False,
            "error": "לא ניתן להמיר כספים ממעסיק נוכחי. נא לבצע סיום עבודה במסך מעסיק נוכחי",
            "pension_tax": "taxable",
            "capital_tax": None,
        },
        "פיצויים_לאחר_התחשבנות": {
            "pension": True,
            "capital_asset": True,
            "pension_tax": "exempt",
            "capital_tax": "capital_gains",
        },
        "פיצויים_שלא_עברו_התחשבנות": {
            "pension": False,
            "capital_asset": False,
            "error": "לא ניתן להמיר כספים שלא עברו התחשבנות",
            "pension_tax": "taxable",
            "capital_tax": None,
        },
        "פיצויים_ממעסיקים_קודמים_רצף_זכויות": {
            "pension": False,
            "capital_asset": False,
            "error": "לא ניתן להמיר כספים ברצף זכויות. נא לבצע התחשבנות כולל במסגרת סיום עבודה מעסיק נוכחי",
            "pension_tax": "taxable",
            "capital_tax": None,
        },
        "פיצויים_ממעסיקים_קודמים_רצף_קצבה": {
            "pension": True,
            "capital_asset": False,
            "error": "לא ניתן להמיר רכיב זה להון",
            "pension_tax": "taxable",
            "capital_tax": None,
        },
        "תגמולי_עובד_עד_2000": {
            "pension": True,
            "capital_asset": True,
            "pension_tax": "exempt",
            "capital_tax": "exempt",
        },
        "תגמולי_מעביד_עד_2000": {
            "pension": True,
            "capital_asset": True,
            "pension_tax": "exempt",
            "capital_tax": "exempt",
        },
        "תגמולי_עובד_אחרי_2000": {
            "pension": True,
            "capital_asset": False,
            "error": "לא ניתן להמיר רכיב זה להון",
            "pension_tax": "taxable",
            "capital_tax": None,
        },
        "תגמולי_מעביד_אחרי_2000": {
            "pension": True,
            "capital_asset": False,
            "error": "לא ניתן להמיר רכיב זה להון",
            "pension_tax": "taxable",
            "capital_tax": None,
        },
        "תגמולי_עובד_אחרי_2008_לא_משלמת": {
            "pension": True,
            "capital_asset": False,
            "error": "לא ניתן להמיר רכיב זה להון",
            "pension_tax": "taxable",
            "capital_tax": None,
        },
        "תגמולי_מעביד_אחרי_2008_לא_משלמת": {
            "pension": True,
            "capital_asset": False,
            "error": "לא ניתן להמיר רכיב זה להון",
            "pension_tax": "taxable",
            "capital_tax": None,
        },
        "קרן_השתלמות": {
            "pension": True,
            "capital_asset": True,
            "pension_tax": "exempt",
            "capital_tax": "exempt",
        },
    }

    if field == "תגמולים":
        if "קרן פנסיה" in pt or "ביטוח" in pt:
            if conversion_type == "capital_asset":
                return False, None, "לא ניתן להמיר רכיב תגמולים להון עבור קרן פנסיה/ביטוח מנהלים"
            return True, "taxable", None

        if "קופת גמל" in pt and "להשקעה" not in pt:
            if conversion_type == "capital_asset":
                return True, "exempt", None
            return True, "exempt", None

        if "גמל להשקעה" in pt:
            if conversion_type == "capital_asset":
                return True, "capital_gains", None
            return True, "exempt", None

        if conversion_type == "capital_asset":
            return False, None, "לא ניתן להמיר רכיב תגמולים להון עבור סוג מוצר לא מזוהה"
        return True, "taxable", None

    rule = rules.get(field)
    if not rule:
        return False, None, f"לא נמצאו חוקים עבור רכיב: {field}"

    can_convert = bool(rule.get(conversion_type))
    if not can_convert:
        return False, None, str(rule.get("error") or f"לא ניתן להמיר רכיב {field}")

    tax_key = "pension_tax" if conversion_type == "pension" else "capital_tax"
    tax = rule.get(tax_key)
    return True, str(tax) if tax is not None else None, None


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


def classify_product_type(*, product_type_str: str, default_conversion_type: str) -> str:
    pt = (product_type_str or "").strip().lower()

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
        default_conversion_type = args.get("default_conversion_type", "pension")

        if not accounts or not isinstance(accounts, list):
            return "Error: חסרה רשימת חשבונות להמרה (accounts)"

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

        converted_pensions = 0
        converted_capitals = 0
        skipped_accounts = 0
        errors = []

        source_pension_funds_zeroed = 0

        unresolved_severance_total = 0.0
        rights_sequence_total = 0.0
        for account in accounts:
            if not isinstance(account, dict):
                continue
            specific_amounts = account.get("specific_amounts")
            if not isinstance(specific_amounts, dict):
                specific_amounts = {}

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

        if unresolved_severance_total > 0 or rights_sequence_total > 0:
            return (
                "Error: לא ניתן להמשיך בתרחיש כל עוד קיימות יתרות בעמודות "
                "'פיצויים שלא עברו התחשבנות' או 'רצף פיצויים מעסיקים קודמים (זכויות)'. "
                "נא לבצע התחשבנות ולרוקן עמודות אלו לפני המשך התרחיש."
            )

        validation_errors: list[str] = []
        normalized_accounts: list[dict] = []

        for idx, account in enumerate(accounts):
            if not isinstance(account, dict):
                validation_errors.append(f"חשבון {idx + 1}: פורמט חשבון לא תקין")
                continue

            account_name = account.get("account_name") or account.get("שם_תכנית", f"חשבון {idx + 1}")
            product_type = account.get("product_type") or account.get("סוג_מוצר", "")
            account_number = account.get("account_number") or account.get("מספר_חשבון") or ""
            if not str(account_number).strip():
                validation_errors.append(f"{account_name}: חסר מספר חשבון (מספר_חשבון) ולכן לא ניתן לבצע המרה בטוחה")
                continue

            specific_amounts = account.get("specific_amounts")
            if not isinstance(specific_amounts, dict):
                specific_amounts = {}

            conversion_type = account.get("conversion_type")
            if not conversion_type:
                conversion_type = classify_product_type(
                    product_type_str=product_type,
                    default_conversion_type=default_conversion_type,
                )

            if conversion_type not in {"pension", "capital_asset"}:
                validation_errors.append(f"{account_name}: conversion_type לא תקין: {conversion_type}")
                continue

            amount_to_convert = 0.0
            if specific_amounts:
                for val in specific_amounts.values():
                    try:
                        amount_to_convert += float(val or 0)
                    except (TypeError, ValueError):
                        continue
            else:
                try:
                    amount_to_convert = float(account.get("balance") or account.get("יתרה") or 0)
                except (TypeError, ValueError):
                    amount_to_convert = 0.0

            if amount_to_convert <= 0:
                skipped_accounts += 1
                continue

            if conversion_type == "capital_asset" and not specific_amounts:
                pt_lower = (product_type or "").lower()
                if not (
                    "השתלמות" in pt_lower
                    or "גמל להשקעה" in pt_lower
                    or ("קופת גמל" in pt_lower and "להשקעה" not in pt_lower)
                ):
                    validation_errors.append(
                        f"{account_name}: אין פירוט רכיבים ולכן אסור להמיר להון עבור סוג מוצר זה ({product_type})"
                    )
                    continue

            for field, val in specific_amounts.items():
                try:
                    numeric_val = float(val or 0)
                except (TypeError, ValueError):
                    numeric_val = 0.0

                ok, _tax, err_msg = _validate_component_conversion(
                    field=field,
                    amount=numeric_val,
                    conversion_type=conversion_type,
                    product_type=product_type,
                )
                if not ok and err_msg:
                    validation_errors.append(f"{account_name}: {err_msg} ({field})")

            normalized_accounts.append(
                {
                    "raw": account,
                    "account_name": account_name,
                    "product_type": product_type,
                    "company": account.get("company") or account.get("חברה_מנהלת", ""),
                    "account_number": str(account_number).strip(),
                    "conversion_type": conversion_type,
                    "amount_to_convert": amount_to_convert,
                }
            )

        if validation_errors:
            return "Error: שגיאות ולידציה בהמרה:\n" + "\n".join(validation_errors)

        for idx, normalized in enumerate(normalized_accounts):
            try:
                account = normalized.get("raw") or {}
                account_name = normalized.get("account_name")
                balance = float(normalized.get("amount_to_convert") or 0)
                product_type = normalized.get("product_type")
                company = normalized.get("company")
                conversion_type = normalized.get("conversion_type")

                logger.info(
                    "🔄 Converting account: name=%s, type=%s, balance=%.2f -> %s",
                    account_name,
                    product_type,
                    balance,
                    conversion_type,
                )

                if conversion_type == "pension":
                    # Convert to pension fund
                    tax_treatment = "exempt" if "השתלמות" in product_type else "taxable"

                    account_number = normalized.get("account_number") or ""

                    if account_number:
                        conflicting_capital_assets = (
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
                            .all()
                        )
                        for existing_conflict in conflicting_capital_assets:
                            db.delete(existing_conflict)

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
                            target_year=retirement_year,
                            birth_date=getattr(client_obj, "birth_date", None),
                            pension_start_date=retirement_date,
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
                            "account_number": account_number,
                            "account_name": account_name,
                            "company": company,
                            "product_type": product_type,
                            "start_date": start_date_raw,
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
                        existing_pf.pension_start_date = retirement_date or date_type(
                            retirement_year, 1, 1
                        )
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
                            pension_start_date=retirement_date
                            or date_type(retirement_year, 1, 1),
                            indexation_method="none",
                            tax_treatment=tax_treatment,
                            deduction_file=account_number or None,
                            conversion_source=conversion_source_json,
                            remarks=f"הומר מתיק פנסיוני - {company}",
                        )
                        db.add(pf)
                    converted_pensions += 1

                    if account_number:
                        source_pension_funds_zeroed += _zero_source_portfolio_pension_funds(
                            db=db,
                            client_id=client_id,
                            account_number=account_number,
                        )

                else:  # capital_asset
                    # Convert to capital asset
                    # Determine asset type based on product
                    if "השתלמות" in product_type:
                        asset_type = "education_fund"
                        tax_treatment = "exempt"
                    elif "גמל" in product_type:
                        asset_type = "provident_fund"
                        tax_treatment = "taxable"
                    else:
                        asset_type = "savings_account"
                        tax_treatment = "taxable"

                    account_number = account.get("account_number") or account.get("מספר_חשבון") or ""

                    if account_number:
                        conflicting_pension_funds = (
                            db.query(PensionFund)
                            .filter(
                                PensionFund.client_id == client_id,
                                PensionFund.deduction_file == account_number,
                                PensionFund.conversion_source.isnot(None),
                                PensionFund.conversion_source.like(
                                    '%"source": "llm_transform_funds_to_assets"%'
                                ),
                            )
                            .all()
                        )
                        for existing_conflict in conflicting_pension_funds:
                            db.delete(existing_conflict)

                    start_date_raw = (
                        account.get("start_date")
                        or account.get("תאריך_התחלה")
                        or account.get("תאריך התחלה")
                    )
                    start_date_obj: Optional[date_type] = _parse_date_value(start_date_raw)
                    payment_date = retirement_date or date_type(retirement_year, 1, 1)

                    conversion_source_json = json.dumps(
                        {
                            "source": "llm_transform_funds_to_assets",
                            "account_number": account_number,
                            "account_name": account_name,
                            "company": company,
                            "product_type": product_type,
                            "start_date": start_date_raw,
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
                    converted_capitals += 1

                    if account_number:
                        source_pension_funds_zeroed += _zero_source_portfolio_pension_funds(
                            db=db,
                            client_id=client_id,
                            account_number=account_number,
                        )

            except Exception as acc_err:
                errors.append(f"שגיאה בחשבון {account_name}: {str(acc_err)}")
                logger.error("Error converting account %s: %s", account_name, acc_err)

        db.commit()

        total_converted = converted_pensions + converted_capitals

        # Clear in-memory pension_portfolio_data to prevent duplicates
        # Note: The original maslaka data is stored in memory (pension_portfolio_data) and in Scenario.parameters,
        # NOT as separate DB records. So we clear the memory and the scenario parameters.
        memory_cleared = False
        if total_converted > 0 and hasattr(agent_tools, "pension_portfolio_data"):
            original_count = (
                len(agent_tools.pension_portfolio_data)
                if agent_tools.pension_portfolio_data
                else 0
            )
            agent_tools.pension_portfolio_data = None
            logger.info(
                "🧹 Cleared pension_portfolio_data from agent service (was %d accounts) to prevent duplicates",
                original_count,
            )

        scenario_source_cleanup_ok = True
        scenarios_updated = 0
        if total_converted > 0:
            try:
                scenarios = db.query(Scenario).filter(Scenario.client_id == client_id).all()
                for scenario in scenarios:
                    if not scenario.parameters:
                        continue
                    try:
                        params = (
                            json.loads(scenario.parameters)
                            if isinstance(scenario.parameters, str)
                            else scenario.parameters
                        )
                        if not isinstance(params, dict):
                            continue

                        portfolio = params.get("pension_portfolio")
                        if isinstance(portfolio, list) and portfolio:
                            params["pension_portfolio"] = []
                            params["pension_portfolio_disabled"] = True
                            params["pension_portfolio_disabled_reason"] = "converted_to_assets"
                            params["pension_portfolio_disabled_at"] = datetime.now().isoformat()
                            scenario.parameters = json.dumps(params, ensure_ascii=False)
                            scenarios_updated += 1
                    except Exception:
                        continue

                if scenarios_updated > 0:
                    db.commit()
                    logger.info(
                        "🧹 Cleared saved pension_portfolio from %d scenarios for client %s after conversion",
                        scenarios_updated,
                        client_id,
                    )
            except Exception as scenario_cleanup_err:
                scenario_source_cleanup_ok = False
                db.rollback()
                logger.warning(
                    "Failed to clear saved pension_portfolio from scenarios for client %s: %s",
                    client_id,
                    scenario_cleanup_err,
                )

        response = {
            "success": True,
            "message": f"✅ הומרו בהצלחה {total_converted} חשבונות: {converted_pensions} נכסי קצבה, {converted_capitals} נכסי הון.",
            "converted_pensions": converted_pensions,
            "converted_capitals": converted_capitals,
            "total_converted": total_converted,
            "skipped_zero_balance": skipped_accounts,
            "errors": errors if errors else None,
            "next_step": "כעת ניתן להפיק דוח באמצעות GENERATE_FULL_REPORT" if total_converted > 0 else None,
            "source_data_cleared": total_converted > 0,
            "memory_cleared": total_converted > 0,
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
        return f"Error: שגיאה בהמרת הכספים: {str(e)}"
