"""
Backward compatibility wrapper for tax_constants.
קובץ תאימות לאחור - מפנה למבנה החדש.

⚠️ קובץ זה נשמר לתאימות לאחור בלבד.
⚠️ עבור קוד חדש, השתמש ב: from app.services.tax.constants import ...

הקובץ המקורי פוצל למודולים קטנים יותר תחת:
app/services/tax/constants/
"""

# Re-export all items from the new structure for backward compatibility
from .tax.constants import (
    DAYS_IN_YEAR,
    HEALTH_TAX_2024,
    HEALTH_TAX_2025,
    HEALTH_TAX_2026,
    INCOME_TAX_BRACKETS_2024,
    INCOME_TAX_BRACKETS_2025,
    INCOME_TAX_BRACKETS_2026,
    INCOME_TYPES,
    INDEXATION_RATES,
    MARITAL_STATUS,
    MONTHS_IN_YEAR,
    NATIONAL_INSURANCE_2024,
    NATIONAL_INSURANCE_2025,
    NATIONAL_INSURANCE_2026,
    PENSION_TAX_EXEMPTIONS,
    SPECIAL_TAX_RATES,
    TAX_CREDIT_POINT_VALUE,
    TAX_CREDITS_2024,
    TAX_CREDITS_2025,
    TAX_CREDITS_2026,
    TaxBracket,
    TaxConstants,
    TaxCredit,
)

__all__ = [
    "TaxBracket",
    "TaxCredit",
    "TaxConstants",
    "INCOME_TAX_BRACKETS_2024",
    "INCOME_TAX_BRACKETS_2025",
    "INCOME_TAX_BRACKETS_2026",
    "NATIONAL_INSURANCE_2024",
    "NATIONAL_INSURANCE_2025",
    "NATIONAL_INSURANCE_2026",
    "HEALTH_TAX_2024",
    "HEALTH_TAX_2025",
    "HEALTH_TAX_2026",
    "TAX_CREDITS_2024",
    "TAX_CREDITS_2025",
    "TAX_CREDITS_2026",
    "TAX_CREDIT_POINT_VALUE",
    "PENSION_TAX_EXEMPTIONS",
    "SPECIAL_TAX_RATES",
    "INDEXATION_RATES",
    "INCOME_TYPES",
    "MARITAL_STATUS",
    "MONTHS_IN_YEAR",
    "DAYS_IN_YEAR",
]
