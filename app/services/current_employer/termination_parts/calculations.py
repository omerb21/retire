import logging
from typing import Dict, Any
from datetime import date
from decimal import Decimal

logger = logging.getLogger("app.current_employer.termination")


def _calculate_employment_years(self, start_date: date, end_date: date) -> float:
    """
    D4.3: חישוב שנות עבודה מלאות

    Args:
        start_date: תאריך תחילת עבודה
        end_date: תאריך סיום עבודה

    Returns:
        מספר שנות העבודה (כולל חלקי שנה)
    """
    if not start_date or not end_date:
        return 0.0

    # חישוב ההפרש בימים וחלוקה ב-365.25 (ממוצע שנה כולל שנים מעוברות)
    days_diff = (end_date - start_date).days
    years = days_diff / 365.25

    return max(0.0, years)


def _calculate_capital_tax(
    self, gross_amount: float, spread_years: int
) -> Dict[str, Any]:
    """
    D4.2: חישוב מס שולי על מענק הוני עם פריסת מס

    Args:
        gross_amount: סכום ברוטו של המענק
        spread_years: מספר שנות פריסה

    Returns:
        Dict עם פרטי המס: total_tax, net_amount, annual_portion, annual_tax, effective_rate
    """
    from app.services.tax.constants import TaxConstants

    if spread_years <= 0:
        spread_years = 1

    # חלוקה שווה של הסכום על השנים
    annual_portion = gross_amount / spread_years

    # חישוב מס שנתי לפי מדרגות מס 2025
    tax_brackets = TaxConstants.INCOME_TAX_BRACKETS_2025

    annual_tax = Decimal("0")
    remaining_income = Decimal(str(annual_portion))
    prev_threshold = Decimal("0")

    for bracket in tax_brackets:
        if remaining_income <= 0:
            break

        threshold = Decimal(str(bracket.max_income)) if bracket.max_income else None
        rate = Decimal(str(bracket.rate))

        if threshold is None:
            # מדרגה אחרונה
            annual_tax += remaining_income * rate
            break

        income_in_bracket = min(remaining_income, threshold - prev_threshold)
        annual_tax += income_in_bracket * rate
        remaining_income -= income_in_bracket
        prev_threshold = threshold

    # סה"כ מס = מס שנתי × מספר שנים
    total_tax = float(annual_tax) * spread_years
    net_amount = gross_amount - total_tax
    effective_rate = (total_tax / gross_amount * 100) if gross_amount > 0 else 0

    logger.debug(
        "Capital tax calculation (gross=%s, spread_years=%s, annual_portion=%s, annual_tax=%s, total_tax=%s, net=%s, effective_rate=%s)",
        gross_amount,
        spread_years,
        annual_portion,
        float(annual_tax),
        total_tax,
        net_amount,
        effective_rate,
    )

    return {
        "gross_amount": gross_amount,
        "spread_years": spread_years,
        "annual_portion": round(annual_portion, 2),
        "annual_tax": round(float(annual_tax), 2),
        "total_tax": round(total_tax, 2),
        "net_amount": round(net_amount, 2),
        "effective_rate": round(effective_rate, 2),
    }
