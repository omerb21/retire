"""
Calculation utilities for retirement scenarios
פונקציות חישוב לתרחישי פרישה
"""

import logging
from datetime import date
from typing import Optional

from app.models.client import Client

from ..constants import DEFAULT_DISCOUNT_RATE, MAX_AGE_FOR_NPV

logger = logging.getLogger("app.scenarios.calculation")


def calculate_years_to_age(
    client: Optional[Client], retirement_age: int, target_age: int = MAX_AGE_FOR_NPV
) -> int:
    """
    מחשב מספר שנים מגיל פרישה עד גיל יעד

    Args:
        client: אובייקט לקוח
        retirement_age: גיל פרישה
        target_age: גיל יעד (ברירת מחדל: 90)

    Returns:
        מספר שנים
    """
    if not client or not client.birth_date:
        # ברירת מחדל אם אין תאריך לידה
        return max(1, target_age - retirement_age)

    years_to_target = max(1, int(target_age - retirement_age))
    return years_to_target


def calculate_npv_dcf(
    monthly_pension: float,
    monthly_additional: float,
    capital: float,
    years: int,
    discount_rate: float = DEFAULT_DISCOUNT_RATE,
) -> float:
    """
    מחשב NPV באמצעות שיטת DCF (Discounted Cash Flow)

    Args:
        monthly_pension: קצבה חודשית
        monthly_additional: הכנסה נוספת חודשית
        capital: הון חד-פעמי
        years: מספר שנים לחישוב
        discount_rate: שיעור היוון שנתי (ברירת מחדל 3%)

    Returns:
        NPV כערך נוכחי נקי

    Note:
        החישוב מבוצע עד גיל 90 של הלקוח.
        ריבית היוון: 3% לשנה (לפי מפרט המערכת)
    """
    logger.info(f"  📊 NPV Calculation: years={years}, discount_rate={discount_rate}")

    # הון חד-פעמי בשנה 0 (לא מהוון)
    npv = float(capital)

    # חישוב חודשי עם היוון חודשי
    monthly_income = monthly_pension + monthly_additional
    monthly_discount_rate = (1 + discount_rate) ** (1 / 12) - 1  # המרה לריבית חודשית

    # הוספת תזרימי מזומנים חודשיים מהוונים
    total_months = years * 12
    for month in range(1, total_months + 1):
        discounted_cashflow = monthly_income / ((1 + monthly_discount_rate) ** month)
        npv += discounted_cashflow

    logger.info(
        f"  💰 NPV Result: total_months={total_months}, monthly_income={monthly_income:.2f}, npv={npv:.2f}"
    )

    return round(npv, 2)
