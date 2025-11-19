"""
Capital utilities for retirement scenarios
פונקציות עזר לטיפול בנכסי הון
"""
import logging
from datetime import date
from decimal import Decimal
from typing import Optional
import json
from app.models.capital_asset import CapitalAsset
from app.models.pension_fund import PensionFund

logger = logging.getLogger("app.scenarios.capital")


def create_capital_asset_from_pension(
    pf: PensionFund,
    client_id: int,
    retirement_year: int,
    partial: bool = False,
    add_action_callback: Optional[callable] = None
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
        logger.warning(f"  ⚠️ Cannot capitalize {pf.fund_name}: missing pension_amount or annuity_factor")
        return None
    
    capital_value = pf.pension_amount * pf.annuity_factor
    
    # שימור יחס מס מהקרן המקורית
    tax_treatment = pf.tax_treatment if pf.tax_treatment else "taxable"
    tax_status = "פטור ממס" if tax_treatment == "exempt" else "חייב במס"
    
    asset_name = f"הון מהיוון {'חלקי ' if partial else ''}{pf.fund_name}"

    # סימון הנכס ההוני כהיוון (COMMUTATION) כדי שיופיע במסך הקצבאות והיוונים
    pension_fund_id = getattr(pf, "id", None)
    remarks = None
    if pension_fund_id is not None:
        remarks = f"COMMUTATION:pension_fund_id={pension_fund_id}&amount={capital_value}"
    
    ca = CapitalAsset(
        client_id=client_id,
        asset_name=asset_name,
        asset_type="provident_fund",
        current_value=Decimal("0"),
        monthly_income=Decimal(str(capital_value)),
        annual_return_rate=Decimal("0.04"),
        payment_frequency="monthly",
        start_date=date(retirement_year, 1, 1),
        indexation_method="none",
        tax_treatment=tax_treatment,
        remarks=remarks,
        conversion_source=json.dumps({
            "source": "scenario_conversion",
            "scenario_type": "retirement",
            "source_type": "pension_fund",
            "source_id": getattr(pf, 'id', None),
            "source_name": pf.fund_name,
            "annuity_factor": float(pf.annuity_factor),
            "partial": partial,
            "tax_treatment": tax_treatment
        })
    )
    
    logger.info(f"  💼 {'Partial' if partial else 'Full'} capitalization: {pf.fund_name} → {capital_value} ₪ capital ({tax_status})")
    
    if add_action_callback:
        add_action_callback(
            "capitalization",
            f"היוון {'חלקי' if partial else 'מלא'} של {pf.fund_name} ({tax_status})",
            from_asset=f"קצבה: {pf.fund_name} ({pf.pension_amount:,.0f} ₪/חודש)",
            to_asset=f"הון: {capital_value:,.0f} ₪ ({tax_status})",
            amount=capital_value
        )
    
    return ca


def capitalize_pension_with_factor(
    pension_amount: float,
    annuity_factor: float,
    client_id: int,
    fund_name: str,
    retirement_year: int,
    tax_treatment: str = "taxable",
    partial: bool = False
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
        current_value=Decimal("0"),
        monthly_income=Decimal(str(capital_value)),
        annual_return_rate=Decimal("0.04"),
        payment_frequency="monthly",
        start_date=date(retirement_year, 1, 1),
        indexation_method="none",
        tax_treatment=tax_treatment,
        conversion_source=json.dumps({
            "source": "scenario_conversion",
            "scenario_type": "retirement",
            "annuity_factor": annuity_factor,
            "partial": partial,
            "tax_treatment": tax_treatment
        })
    )
    
    return ca
