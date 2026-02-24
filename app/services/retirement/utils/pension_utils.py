"""
Pension utilities for retirement scenarios
פונקציות עזר לטיפול בקצבאות
"""

import logging
from datetime import date
from decimal import Decimal
from typing import Optional
from sqlalchemy.orm import Session
from app.models.pension_fund import PensionFund
from app.models.capital_asset import CapitalAsset
from ..constants import PENSION_COEFFICIENT
import json

logger = logging.getLogger("app.scenarios.pension")


def compute_pension_start_date_from_funds(db: Session, client) -> Optional[date]:
    """Calculate earliest pension_start_date from all of the client's pension funds.

    This ignores the value stored on the Client itself and looks only at PensionFund
    records that have a non-null pension_start_date.
    """
    if not client:
        return None

    funds = (
        db.query(PensionFund)
        .filter(
            PensionFund.client_id == client.id,
            PensionFund.pension_start_date.isnot(None),
        )
        .all()
    )

    if not funds:
        return None

    candidates = [fund.pension_start_date for fund in funds if fund.pension_start_date]
    if not candidates:
        return None

    return min(candidates)


def get_effective_pension_start_date(db: Session, client) -> Optional[date]:
    """Return the effective pension start date for a client based on real pensions.

    The date is always derived from the client's PensionFund records. If there are
    no pension funds with a non-null pension_start_date, the function returns None
    even if a client-level pension_start_date field was set manually.
    """
    if not client:
        return None

    return compute_pension_start_date_from_funds(db, client)


def convert_balance_to_pension(
    pf: PensionFund,
    retirement_year: int,
    add_action_callback: Optional[callable] = None,
) -> None:
    """
    המרת יתרה לקצבה

    Args:
        pf: קרן פנסיה
        retirement_year: שנת פרישה
        add_action_callback: פונקציה לרישום פעולה
    """
    if not pf.balance or not pf.annuity_factor:
        logger.warning(
            f"  ⚠️ Cannot convert {pf.fund_name}: missing balance or annuity_factor"
        )
        return

    original_balance = pf.balance
    tax_status = "פטור ממס" if pf.tax_treatment == "exempt" else "חייב במס"

    # חישוב קצבה
    pf.pension_amount = float(pf.balance) / float(pf.annuity_factor)
    pf.pension_start_date = date(retirement_year, 1, 1)

    logger.info(
        f"  💰 Converted {pf.fund_name}: Balance {pf.balance} → Pension {pf.pension_amount} ({tax_status})"
    )

    if add_action_callback:
        add_action_callback(
            "conversion",
            f"המרת יתרה לקצבה: {pf.fund_name} ({tax_status})",
            from_asset=f"יתרה: {original_balance:,.0f} ₪",
            to_asset=f"קצבה: {pf.pension_amount:,.0f} ₪/חודש ({tax_status})",
            amount=float(original_balance or 0),
        )


def convert_capital_to_pension(
    ca: CapitalAsset,
    client_id: int,
    retirement_year: int,
    db: Session,
    add_action_callback: Optional[callable] = None,
) -> PensionFund:
    """
    המרת נכס הון לקצבה

    Args:
        ca: נכס הון
        client_id: מזהה לקוח
        retirement_year: שנת פרישה
        db: סשן מסד נתונים
        add_action_callback: פונקציה לרישום פעולה

    Returns:
        קרן פנסיה חדשה
    """
    # תוקן: נכסי הון מייצגים תשלום חודשי, לא הון חד-פעמי
    capital_value = float(ca.monthly_income or 0)
    pension_amount = capital_value / PENSION_COEFFICIENT

    # שימור יחס מס מהנכס המקורי
    tax_treatment = ca.tax_treatment if ca.tax_treatment else "taxable"
    tax_status = "פטור ממס" if tax_treatment == "exempt" else "חייב במס"

    pf = PensionFund(
        client_id=client_id,
        fund_name=(
            f"קצבה מ{ca.asset_name}"
            if tax_treatment == "taxable"
            else f"קצבה פטורה מ{ca.asset_name}"
        ),
        fund_type="converted_capital",
        input_mode="manual",
        pension_amount=pension_amount,
        pension_start_date=date(retirement_year, 1, 1),
        indexation_method="none",
        tax_treatment=tax_treatment,
        conversion_source=json.dumps(
            {
                "source_type": "capital_asset",
                "source_id": getattr(ca, "id", None),
                "source_name": ca.asset_name,
                "original_value": capital_value,
                "tax_treatment": tax_treatment,
            },
            ensure_ascii=False,
        ),
    )

    logger.info(
        f"  Converted capital asset '{ca.asset_name}': {capital_value} → {tax_status} Pension {pension_amount}"
    )

    if add_action_callback:
        add_action_callback(
            "conversion",
            f"המרת נכס הון לקצבה: {ca.asset_name} ({tax_status})",
            from_asset=f"הון: {ca.asset_name} ({capital_value:,.0f} ₪)",
            to_asset=f"קצבה: {pension_amount:,.0f} ₪/חודש ({tax_status})",
            amount=capital_value,
        )

    return pf


def convert_education_fund_to_pension(
    ef: PensionFund,
    retirement_year: int,
    add_action_callback: Optional[callable] = None,
) -> None:
    """
    המרת קרן השתלמות לקצבה פטורה

    Args:
        ef: קרן השתלמות
        retirement_year: שנת פרישה
        add_action_callback: פונקציה לרישום פעולה
    """
    original_balance = ef.balance

    if not original_balance or original_balance <= 0:
        logger.warning(f"  Education fund {ef.fund_name} has no balance, skipping")
        return

    # שימוש במקדם דינמי אם קיים, אחרת נפילה לברירת המחדל
    annuity_factor = (
        float(ef.annuity_factor)
        if getattr(ef, "annuity_factor", None)
        else PENSION_COEFFICIENT
    )

    # המרה לקצבה פטורה
    pension_amount = float(original_balance) / float(annuity_factor)

    # עדכון הקרן הקיימת במקום יצירת חדשה
    ef.pension_amount = pension_amount
    ef.pension_start_date = date(retirement_year, 1, 1)
    ef.annuity_factor = annuity_factor
    ef.fund_type = "education_fund_pension"

    logger.info(
        f"  Converted education fund '{ef.fund_name}': {original_balance} → Exempt PENSION {pension_amount} ₪/month"
    )

    if add_action_callback:
        add_action_callback(
            "conversion",
            f"המרת קרן השתלמות לקצבה פטורה: {ef.fund_name}",
            from_asset=f"קרן השתלמות: {ef.fund_name} ({original_balance:,.0f} ₪)",
            to_asset=f"קצבה פטורה: {pension_amount:,.0f} ₪/חודש",
            amount=float(original_balance),
        )


def convert_education_fund_to_capital(
    ef: PensionFund,
    client_id: int,
    retirement_year: int,
    add_action_callback: Optional[callable] = None,
) -> CapitalAsset:
    """
    המרת קרן השתלמות להון פטור

    Args:
        ef: קרן השתלמות
        client_id: מזהה לקוח
        retirement_year: שנת פרישה
        add_action_callback: פונקציה לרישום פעולה

    Returns:
        נכס הון חדש
    """
    original_balance = ef.balance

    if not original_balance or original_balance <= 0:
        logger.warning(f"  Education fund {ef.fund_name} has no balance, skipping")
        return None

    # יצירת נכס הוני פטור
    ca = CapitalAsset(
        client_id=client_id,
        asset_name=f"הון פטור מ{ef.fund_name}",
        asset_type="education_fund",
        current_value=Decimal(str(original_balance)),
        monthly_income=Decimal("0"),
        annual_return_rate=Decimal("0.04"),
        payment_frequency="annually",
        start_date=date(retirement_year, 1, 1),
        indexation_method="none",
        tax_treatment="exempt",
        conversion_source=json.dumps(
            {
                "source": "scenario_conversion",
                "scenario_type": "retirement",
                "source_type": "education_fund",
                "source_id": getattr(ef, "id", None),
                "source_name": ef.fund_name,
                "original_balance": float(original_balance),
                "tax_treatment": "exempt",
            },
            ensure_ascii=False,
        ),
    )

    logger.info(
        f"  Converted education fund '{ef.fund_name}': {original_balance} → Exempt CAPITAL {original_balance} ₪"
    )

    if add_action_callback:
        add_action_callback(
            "conversion",
            f"המרת קרן השתלמות להון פטור: {ef.fund_name}",
            from_asset=f"קרן השתלמות: {ef.fund_name} ({original_balance:,.0f} ₪)",
            to_asset=f"הון פטור: {original_balance:,.0f} ₪",
            amount=float(original_balance),
        )

    return ca
