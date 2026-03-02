"""
Capital utilities for retirement scenarios
פונקציות עזר לטיפול בנכסי הון
"""

import json
import logging
from datetime import date
from decimal import Decimal
from typing import Optional

from app.models.capital_asset import CapitalAsset
from app.models.pension_fund import PensionFund

logger = logging.getLogger("app.scenarios.capital")


def create_capital_asset_from_pension(
    pf: PensionFund,
    client_id: int,
    retirement_year: int,
    partial: bool = False,
    add_action_callback: Optional[callable] = None,
) -> CapitalAsset:
    """
    יצירת נכס הון מקרן פנסיה

    Args:
        pf: קרן פנסיה
        client_id: מזהה לקוח
        retirement_year: שנת פרישה
        partial: האם זו המרה חלקית
        add_action_callback: פונקציה לרישום פעולה

    Returns:
        נכס הון חדש
    """
    if not pf.pension_amount or not pf.annuity_factor:
        logger.warning(
            f"  ⚠️ Cannot capitalize {pf.fund_name}: missing pension_amount or annuity_factor"
        )
        return None

    capital_value = pf.pension_amount * pf.annuity_factor

    # צילום הקצבה המקורית לפני ההיוון – לצורך שחזור מדויק במקרה של מחיקת ההיוון
    original_pension_snapshot = {
        "id": getattr(pf, "id", None),
        "fund_name": getattr(pf, "fund_name", None),
        "fund_type": getattr(pf, "fund_type", None),
        "input_mode": (
            str(getattr(pf, "input_mode", None))
            if getattr(pf, "input_mode", None) is not None
            else None
        ),
        "balance": (
            float(pf.balance) if getattr(pf, "balance", None) is not None else None
        ),
        "annuity_factor": (
            float(pf.annuity_factor)
            if getattr(pf, "annuity_factor", None) is not None
            else None
        ),
        "pension_amount": (
            float(pf.pension_amount)
            if getattr(pf, "pension_amount", None) is not None
            else None
        ),
        "pension_start_date": (
            pf.pension_start_date.isoformat()
            if getattr(pf, "pension_start_date", None)
            else None
        ),
        "indexation_method": (
            str(getattr(pf, "indexation_method", None))
            if getattr(pf, "indexation_method", None) is not None
            else None
        ),
        "tax_treatment": getattr(pf, "tax_treatment", None),
        "deduction_file": getattr(pf, "deduction_file", None),
        "remarks": getattr(pf, "remarks", None),
    }

    # שימור יחס מס מהקרן המקורית
    tax_treatment = pf.tax_treatment if pf.tax_treatment else "taxable"
    tax_status = "פטור ממס" if tax_treatment == "exempt" else "חייב במס"

    asset_name = f"הון מהיוון {'חלקי ' if partial else ''}{pf.fund_name}"

    # סימון הנכס ההוני כהיוון (COMMUTATION) כדי שיופיע במסך הקצבאות והיוונים
    pension_fund_id = getattr(pf, "id", None)
    remarks = None
    if pension_fund_id is not None:
        remarks = (
            f"COMMUTATION:pension_fund_id={pension_fund_id}&amount={capital_value}"
        )

    ca = CapitalAsset(
        client_id=client_id,
        asset_name=asset_name,
        asset_type="provident_fund",
        current_value=Decimal(str(capital_value)),
        monthly_income=Decimal("0"),
        annual_return_rate=Decimal("0.04"),
        payment_frequency="annually",
        start_date=date(retirement_year, 1, 1),
        indexation_method="none",
        tax_treatment=tax_treatment,
        remarks=remarks,
        conversion_source=json.dumps(
            {
                "source": "scenario_conversion",  # מאפשר זיהוי בתרחישים
                "scenario_type": "retirement",
                "source_type": "pension_fund",
                "type": "pension_commutation",  # מאפשר שחזור כמו במסך הקצבאות
                "pension_fund_id": getattr(pf, "id", None),
                "source_id": getattr(pf, "id", None),
                "source_name": pf.fund_name,
                "annuity_factor": (
                    float(pf.annuity_factor)
                    if getattr(pf, "annuity_factor", None) is not None
                    else None
                ),
                "partial": partial,
                "tax_treatment": tax_treatment,
                "original_pension": original_pension_snapshot,
            },
            ensure_ascii=False,
        ),
    )

    logger.info(
        f"  💼 {'Partial' if partial else 'Full'} capitalization: {pf.fund_name} → {capital_value} ₪ capital ({tax_status})"
    )

    if add_action_callback:
        add_action_callback(
            "capitalization",
            f"היוון {'חלקי' if partial else 'מלא'} של {pf.fund_name} ({tax_status})",
            from_asset=f"קצבה: {pf.fund_name} ({pf.pension_amount:,.0f} ₪/חודש)",
            to_asset=f"הון: {capital_value:,.0f} ₪ ({tax_status})",
            amount=capital_value,
        )

    return ca


def capitalize_pension_with_factor(
    pension_amount: float,
    annuity_factor: float,
    client_id: int,
    fund_name: str,
    retirement_year: int,
    tax_treatment: str = "taxable",
    partial: bool = False,
) -> CapitalAsset:
    """
    המרת קצבה להון עם מקדם נתון

    Args:
        pension_amount: סכום קצבה חודשי
        annuity_factor: מקדם קצבה
        client_id: מזהה לקוח
        fund_name: שם הקרן
        retirement_year: שנת פרישה
        tax_treatment: יחס מס
        partial: האם זו המרה חלקית

    Returns:
        נכס הון חדש
    """
    capital_value = pension_amount * annuity_factor

    ca = CapitalAsset(
        client_id=client_id,
        asset_name=f"הון מהיוון {'חלקי ' if partial else ''}{fund_name}",
        asset_type="provident_fund",
        current_value=Decimal(str(capital_value)),
        monthly_income=Decimal("0"),
        annual_return_rate=Decimal("0.04"),
        payment_frequency="annually",
        start_date=date(retirement_year, 1, 1),
        indexation_method="none",
        tax_treatment=tax_treatment,
        conversion_source=json.dumps(
            {
                "source": "scenario_conversion",
                "scenario_type": "retirement",
                "annuity_factor": annuity_factor,
                "partial": partial,
                "tax_treatment": tax_treatment,
            },
            ensure_ascii=False,
        ),
    )

    return ca
